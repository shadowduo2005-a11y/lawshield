"""
Comprehensive test suite for Phase 15 (Agent-to-Agent Communication).

Tests cover the registry, priority queue, event bus, memory logs, dispatcher execution,
pattern-based routing (Pipeline, Parallel), and FastAPI router endpoints.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from main import app
from communication.protocol import MessagePriority, MessageStatus
from communication.message import AgentMessage
from communication.registry import AgentRegistry
from communication.queue import AgentMessageQueue
from communication.events import EventBus
from communication.memory import MessageMemory
from communication.broker import MessageBroker
from communication.dispatcher import MessageDispatcher
from communication.router import run_pipeline, run_parallel


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry()
        self.registry.clear()

    def test_register_and_lookup_valid_agent(self):
        handler = lambda x: {"res": "ok"}
        self.registry.register("Research", handler, ["search_law"])
        
        self.assertIn("Research", self.registry.list_agents())
        self.assertEqual(self.registry.get_handler("Research"), handler)

    def test_register_invalid_agent_throws_error(self):
        with self.assertRaises(ValueError):
            self.registry.register("IllegalAgentName", lambda x: x)


class TestPriorityQueue(unittest.TestCase):
    def test_priority_ordering(self):
        q = AgentMessageQueue()
        
        m_low = AgentMessage(sender="S", receiver="R", task="T1", priority=MessagePriority.LOW)
        m_high = AgentMessage(sender="S", receiver="R", task="T2", priority=MessagePriority.HIGH)
        m_med = AgentMessage(sender="S", receiver="R", task="T3", priority=MessagePriority.MEDIUM)
        
        q.push(m_low)
        q.push(m_high)
        q.push(m_med)
        
        # Must pop HIGH, then MEDIUM, then LOW
        self.assertEqual(q.pop().id, m_high.id)
        self.assertEqual(q.pop().id, m_med.id)
        self.assertEqual(q.pop().id, m_low.id)


class TestEventBus(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.bus.clear()

    def test_publish_subscribe(self):
        call_count = 0
        def callback(msg):
            nonlocal call_count
            call_count += 1
            self.assertEqual(msg.payload["data"], "hello")

        self.bus.subscribe("contract_updates", callback)
        
        msg = AgentMessage(sender="S", receiver="topic:contract_updates", task="E", payload={"data": "hello"})
        self.bus.publish("contract_updates", msg)
        
        self.assertEqual(call_count, 1)


class TestMemoryLogs(unittest.TestCase):
    def setUp(self):
        self.memory = MessageMemory()
        self.memory.clear()

    def test_record_and_filter(self):
        m1 = AgentMessage(sender="Research", receiver="Citation", task="T1")
        m2 = AgentMessage(sender="Citation", receiver="Research", task="T2")
        
        self.memory.record(m1)
        self.memory.record(m2)
        
        self.assertEqual(len(self.memory.get_history()), 2)
        self.assertEqual(len(self.memory.get_history(sender="Research")), 1)
        self.assertEqual(self.memory.get_history(sender="Research")[0].task, "T1")


class TestDispatcher(unittest.TestCase):
    def setUp(self):
        self.broker = MessageBroker()
        self.broker.registry.clear()
        self.broker.memory.clear()
        self.dispatcher = MessageDispatcher(self.broker)

    def test_dispatch_direct_and_reply_flow(self):
        # Register sender (Research) and receiver (Citation)
        self.broker.register_agent("Citation", lambda payload: {"citations": ["Sec 54"]}, ["cite"])
        self.broker.register_agent("Research", lambda payload: {"done": True})

        msg = AgentMessage(
            sender="Research",
            receiver="Citation",
            task="Find citation",
            payload={"section": "54"},
            reply_to="Research"  # Reply is routed back
        )
        
        self.broker.send_message(msg)
        self.assertEqual(self.broker.queue.size(), 1)
        
        # Process message
        processed = self.dispatcher.process_next()
        self.assertTrue(processed)
        self.assertEqual(msg.status, MessageStatus.PROCESSED)

        # The dispatcher should have automatically queued a reply to 'Research'
        self.assertEqual(self.broker.queue.size(), 1)
        reply = self.broker.queue.pop()
        self.assertEqual(reply.sender, "Citation")
        self.assertEqual(reply.receiver, "Research")
        self.assertEqual(reply.payload["citations"], ["Sec 54"])


class TestPatterns(unittest.TestCase):
    def setUp(self):
        self.broker = MessageBroker()
        self.broker.registry.clear()
        self.broker.memory.clear()
        self.dispatcher = MessageDispatcher(self.broker)
        
        # Setup shared references in modules
        from communication.router import broker as r_broker, dispatcher as r_dispatcher
        r_broker.registry.clear()
        r_broker.memory.clear()

    def test_pipeline_pattern(self):
        # Register agents in router's broker
        from communication.router import broker as r_broker
        r_broker.register_agent("Research", lambda payload: {"step": payload["step"] + " -> Research"})
        r_broker.register_agent("Drafting", lambda payload: {"step": payload["step"] + " -> Drafting"})

        res = run_pipeline(["Research", "Drafting"], {"step": "Start"})
        self.assertEqual(res["step"], "Start -> Research -> Drafting")

    def test_parallel_pattern(self):
        from communication.router import broker as r_broker
        r_broker.register_agent("Compliance", lambda payload: {"check": "compliant"})
        r_broker.register_agent("Calculator", lambda payload: {"sum": 42})

        res = run_parallel(["Compliance", "Calculator"], {"data": "input"})
        
        self.assertIn("Compliance", res)
        self.assertEqual(res["Compliance"]["check"], "compliant")
        self.assertIn("Calculator", res)
        self.assertEqual(res["Calculator"]["sum"], 42)


class TestFastApiCommunication(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        from communication.router import broker as r_broker
        r_broker.registry.clear()
        r_broker.memory.clear()

    def test_send_and_history_api(self):
        from communication.router import broker as r_broker
        r_broker.register_agent("Research", lambda payload: {"output": "ok"})

        payload = {
            "sender": "Supervisor",
            "receiver": "Research",
            "task": "Perform research",
            "payload": {"query": "law"},
            "priority": "HIGH"
        }
        
        # Send
        response = self.client.post("/communication/send", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "processed")

        # Check logs
        response_hist = self.client.get("/communication/history")
        self.assertEqual(response_hist.status_code, 200)
        logs = response_hist.json()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["sender"], "Supervisor")


if __name__ == "__main__":
    unittest.main()
