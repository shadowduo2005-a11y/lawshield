"""
registry.py – handles dynamic agent registration and discovery.
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, Any, Callable, List, Optional

logger = logging.getLogger(__name__)

# List of allowed dynamic agent names
VALID_AGENTS = {
    "Supervisor",
    "Planner",
    "Research",
    "Citation",
    "Drafting",
    "Compliance",
    "Review",
    "Calculator",
    "Contract",
    "Summarizer",
    "PipelineRouter",
    "ParallelRouter"
}

class AgentRegistry:
    """
    Registry for dynamic discovery and lookup of legal agents.
    """
    _instance: Optional[AgentRegistry] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls, *args, **kwargs)
                cls._instance._registry = {}
                cls._instance._registry_lock = threading.Lock()
        return cls._instance

    def register(self, agent_name: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]], capabilities: Optional[List[str]] = None) -> None:
        """
        Registers an agent and its execution callback handler.
        """
        if agent_name not in VALID_AGENTS:
            raise ValueError(f"Agent '{agent_name}' is not in the allowed valid agents list: {VALID_AGENTS}")

        with self._registry_lock:
            self._registry[agent_name] = {
                "handler": handler,
                "capabilities": capabilities or []
            }
        logger.info("Agent '%s' successfully registered in dynamic registry.", agent_name)

    def get_handler(self, agent_name: str) -> Optional[Callable[[Dict[str, Any]], Dict[str, Any]]]:
        """
        Returns the registered callback handler for an agent.
        """
        with self._registry_lock:
            agent_info = self._registry.get(agent_name)
            return agent_info["handler"] if agent_info else None

    def list_agents(self) -> List[str]:
        """
        Returns a list of all registered agent names.
        """
        with self._registry_lock:
            return list(self._registry.keys())

    def clear(self) -> None:
        """
        Clears the registered agents.
        """
        with self._registry_lock:
            self._registry.clear()
