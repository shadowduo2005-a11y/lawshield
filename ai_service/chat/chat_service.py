"""
ChatService – orchestrates the multi-agent graph with full memory integration.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from graph.graph import create_graph
from llm.providers.factory import get_llm_provider
from legal_guardrails import validate_input, validate_output
from masking.replacement import MaskingState
from memory.conversation import SlidingWindowMemory, get_conversation
from memory.long_term import extract_and_save_facts, get_long_term_facts
from memory.vector import save_to_vector_memory, search_vector_memory

logger = logging.getLogger(__name__)

# Nodes that produce the final answer to be streamed to the user
_TERMINAL_NODES = {"review", "contract", "compliance", "summarizer", "calculator", "reasoning", "qa", "rag"}

# Default blank state — must include ALL keys defined in AgentState so that
# LangGraph can merge partial state updates without KeyError.
_BLANK_STATE = {
    "messages": [],
    "next_node": "",
    "plan": "",
    "research_data": [],
    "draft_content": "",
    "citations": [],
    "review_status": "",
    "contract_analysis": "",
    "compliance_report": "",
    "summary": "",
    "calculation_result": "",
    # Reasoning pipeline fields (missing previously → caused KeyError / state merge crash)
    "reasoning_output": "",
    "reasoning_confidence": 0.0,
    "reasoning_iterations": 0,
}


class ChatService:
    """Wraps the LangGraph multi-agent workflow with masking and memory."""

    def __init__(self, provider_name: str | None = None) -> None:
        self.provider_name = provider_name
        self.graph = create_graph()

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _build_system_message(self, session_id: str, masked_query: str) -> SystemMessage:
        """Compose the system prompt enriched with long-term and vector memory.

        This method is **async** so that the blocking embedding-model load
        (R6 fix: search_vector_memory downloads a 560 MB BGE model on cold start)
        runs inside asyncio.to_thread and never freezes the event loop.
        """
        base = (
            "You are Harvey, a highly advanced Indian legal AI assistant specialised in the laws of India. "
            "Your primary jurisdiction is India. You are an expert in: "
            "the Constitution of India, Indian Penal Code (IPC) / Bharatiya Nyaya Sanhita (BNS), "
            "Code of Criminal Procedure (CrPC) / Bharatiya Nagarik Suraksha Sanhita (BNSS), "
            "Code of Civil Procedure (CPC), Indian Evidence Act / Bharatiya Sakshya Adhiniyam, "
            "Transfer of Property Act, Contract Act 1872, Companies Act 2013, GST laws, "
            "SEBI regulations, RBI guidelines, IT Act 2000, Consumer Protection Act, "
            "RTI Act, labour laws (Industrial Disputes Act, Shops & Establishments Acts), "
            "family law (Hindu Marriage Act, Special Marriage Act, Muslim Personal Law), "
            "intellectual property (Patents Act, Copyright Act, Trade Marks Act), "
            "and relevant judgments of the Supreme Court of India and various High Courts. "
            "When citing authority, prefer Indian statutes, SCOI judgments, and High Court decisions. "
            "Use Indian legal terminology (e.g., 'petition', 'writ', 'FIR', 'Magistrate', 'Sessions Court', 'High Court'). "
            "Be concise, accurate, and always cite your sources. "
            "Be friendly, polite, and conversational when greeted or engaged in pleasantries, and concise, accurate, and authoritative when answering legal questions. "
            "CRITICAL PROFESSIONAL INSTRUCTION: You are a professional Indian legal AI assistant for lawyers and citizens, NOT a child-friendly chatbot. "
            "Users will ask theoretical, hypothetical, real-world, or first-person questions about criminal liability, offenses, murder, assault, theft, penalties, and imprisonment (e.g., 'if I kill someone how long is my imprisonment'). "
            "DO NOT refuse, lecture, preach, or trigger general AI safety refusals or moralizing. "
            "Answer directly, objectively, and authoritatively citing Indian statutes—specifically the Bharatiya Nyaya Sanhita (BNS, 2023) and Indian Penal Code (IPC, 1860) (e.g., explain Section 103 BNS / Section 302 IPC for murder, which prescribes life imprisonment or death). "
            "Under NO circumstances should you EVER output United States emergency hotlines or foreign resources. If emergency help is relevant, mention ONLY Indian support numbers: Police (112), Kiran Mental Health Helpline (1800-599-0019), or Tele-MANAS (14416)."
        )

        # Long-term facts are a cheap in-process dict lookup — safe to call directly
        try:
            facts = get_long_term_facts(session_id)
            if facts:
                base += f"\n\n{facts}"
        except Exception as exc:
            logger.warning("Failed to load long-term facts for session %s: %s", session_id, exc)

        # Vector memory search loads the BGE embedding model on first call (~5 s).
        # Run it in a thread so the event loop stays responsive. (R6 fix)
        try:
            past = await asyncio.to_thread(search_vector_memory, session_id, masked_query, 2)
            if past:
                base += f"\n\nRelevant past conversations:\n{past}"
        except Exception as exc:
            logger.warning("Failed to search vector memory for session %s: %s", session_id, exc)

        return SystemMessage(content=base)

    def _process_history(self, history: list[dict] | None) -> tuple[list, MaskingState]:
        combined_state = MaskingState()
        masked_messages = []
        if history:
            for h_msg in history:
                role = h_msg.get("role", "").lower()
                content = h_msg.get("content", "")

                if role == "user":
                    # Mask user messages and execute guardrail checks, tracking the state
                    masked_content, turn_state = validate_input(content, state=combined_state)
                    combined_state = combined_state.merge(turn_state)
                    masked_messages.append(HumanMessage(content=masked_content))
                elif role == "assistant":
                    # Do NOT mask assistant messages — they were already restored
                    # before being stored, so they contain real names. If we mask
                    # them again, the AI will echo back "<PERSON_1>" in its replies.
                    masked_messages.append(AIMessage(content=content))
        return masked_messages, combined_state

    async def _prepare_state_with_history(self, session_id: str, message: str, history: list[dict] | None = None) -> tuple[dict, SlidingWindowMemory, HumanMessage, MaskingState]:
        """Build the initial graph state and update conversation memory using backend history."""
        # Process history and build combined MaskingState
        masked_history, combined_state = self._process_history(history)

        # Validate and mask the current message using the combined state
        masked_query, turn_state = validate_input(message, state=combined_state)
        combined_state = combined_state.merge(turn_state)

        # _build_system_message is now async (R6 fix)
        sys_msg = await self._build_system_message(session_id, masked_query)

        convo = get_conversation(session_id)
        # Clear convo and rebuild from history to keep it exactly in sync
        convo.clear()
        for msg in masked_history:
            convo.add_message(msg)

        user_msg = HumanMessage(content=masked_query)
        convo.add_message(user_msg)

        messages = [sys_msg] + convo.get_messages()
        state = {**_BLANK_STATE, "messages": messages}

        return state, convo, user_msg, combined_state

    def _commit_memory_background(
        self, session_id: str, convo: SlidingWindowMemory, user_msg: HumanMessage, answer: str
    ) -> None:
        """Save the exchange to memory asynchronously (fire-and-forget).

        Each memory operation is wrapped in its own task so a failure in one
        (e.g. Qdrant is down) does not affect the other or the main response.
        """
        ai_msg = AIMessage(content=answer)
        convo.add_message(ai_msg)

        exchange = f"User: {user_msg.content}\nHarvey: {answer}"

        def _safe_extract():
            try:
                extract_and_save_facts(session_id, exchange)
            except Exception as exc:
                logger.warning("Background fact extraction failed for session %s: %s", session_id, exc)

        def _safe_vector_save():
            try:
                save_to_vector_memory(session_id, [user_msg, ai_msg])
            except Exception as exc:
                logger.warning("Background vector save failed for session %s: %s", session_id, exc)

        try:
            loop = asyncio.get_running_loop()
            # Use asyncio.to_thread so blocking IO doesn't stall the event loop.
            # Each task is independent — failures are swallowed inside the helpers.
            loop.create_task(asyncio.to_thread(_safe_extract))
            loop.create_task(asyncio.to_thread(_safe_vector_save))
        except RuntimeError:
            # No running event loop (e.g., called from a sync unit test)
            _safe_extract()
            _safe_vector_save()

    def _direct_response(self, messages: list, user_question: str | None = None) -> str:
        """Ask the LLM directly (Supervisor chose FINISH — greetings, small-talk, direct Q&A)."""
        try:
            model = get_llm_provider(self.provider_name).get_model()

            greeting_system_prompt = SystemMessage(
                content=(
                    "You are Harvey, a friendly, helpful, and intelligent AI legal assistant for LawShield. "
                    "When the user greets you, introduces themselves, asks about past conversation history, or engages in casual conversation or small talk, "
                    "respond warmly, naturally, and conversationally as a friendly chatbot. "
                    "Always maintain full awareness of past conversation history in this session and answer questions about previous messages accurately. "
                    "Offer to assist them with Indian law, legal queries, contract analysis, or document research. "
                    "CRITICAL PROFESSIONAL INSTRUCTION: You are a professional Indian legal AI assistant for lawyers and citizens, NOT a child-friendly chatbot. "
                    "If asked about criminal liability, murder, violence, or imprisonment (e.g., 'if I kill someone how long is my imprisonment'), DO NOT refuse or provide US crisis hotlines. Answer directly with relevant Indian law provisions under Bharatiya Nyaya Sanhita (BNS, 2023) / IPC."
                )
            )

            # Extract all user/assistant message turns, preserving full history
            non_sys_messages = [m for m in (messages or []) if getattr(m, "type", "") != "system"]
            if not non_sys_messages and user_question:
                non_sys_messages = [HumanMessage(content=user_question)]

            full_messages = [greeting_system_prompt] + non_sys_messages
            return model.invoke(full_messages).content
        except Exception as exc:
            logger.error("Direct LLM response failed: %s", exc)
            raise exc

    # ── public API ────────────────────────────────────────────────────────────

    async def stream_chat(self, session_id: str, message: str, history: list[dict] | None = None) -> AsyncGenerator[str, None]:
        """Stream node-by-node progress then yield the final answer.

        Yields raw strings (no ``data:`` prefix). The router's ``event_generator``
        wraps each chunk in the SSE ``data: …\\n\\n`` envelope.
        """
        state, convo, user_msg, masking_state = await self._prepare_state_with_history(session_id, message, history)
        initial_messages = state["messages"]

        final_answer: str | None = None

        try:
            async for event in self.graph.astream(state):
                for node_name, node_state in event.items():
                    # Yield a progress ping so the frontend knows which node is running
                    yield f"[Node: {node_name}]"

                    if node_name in _TERMINAL_NODES:
                        msgs = node_state.get("messages") or []
                        if msgs:
                            # node_state["messages"] is the *delta* returned by the node
                            # (a list with just the new AIMessage), not the full history
                            last = msgs[-1]
                            if hasattr(last, "content"):
                                final_answer = last.content

                    elif node_name == "supervisor":
                        next_node = node_state.get("next_node", "")
                        if next_node in ("FINISH", "__end__"):
                            # Supervisor decided no specialist agent is needed;
                            # answer directly from the conversation context
                            final_answer = self._direct_response(initial_messages, user_question=message)

        except Exception as exc:
            logger.exception("Error during graph streaming for session %s: %s", session_id, exc)
            raise exc

        if final_answer is None:
            # Fallback: supervisor routed to END or graph produced no AI message
            final_answer = self._direct_response(initial_messages, user_question=message)

        # Persist exchange to memory (non-blocking)
        self._commit_memory_background(session_id, convo, user_msg, final_answer)

        # Validate output via Guardrails (citation verification, leak prevention) and restore PII
        restored = validate_output(final_answer, state=masking_state, user_question=message)
        yield "[FINAL]"
        yield restored
        yield "[DONE]"

    async def chat(self, session_id: str, message: str, history: list[dict] | None = None) -> str:
        """Non-streaming chat; returns the final text response."""
        state, convo, user_msg, masking_state = await self._prepare_state_with_history(session_id, message, history)
        initial_messages = state["messages"]

        try:
            final_state = await self.graph.ainvoke(state)
        except Exception as exc:
            logger.exception("Graph invocation failed for session %s: %s", session_id, exc)
            # Fall back to a direct LLM call rather than returning an empty response
            answer = self._direct_response(initial_messages, user_question=message)
            self._commit_memory_background(session_id, convo, user_msg, answer)
            return validate_output(answer, state=masking_state, user_question=message)

        all_messages = final_state.get("messages") or []
        # Slice off the initial messages we sent in; only look at newly added ones
        new_messages = all_messages[len(initial_messages):]
        ai_messages = [m for m in new_messages if isinstance(m, AIMessage)]

        if ai_messages:
            final_msg = ai_messages[-1].content
        else:
            final_msg = self._direct_response(initial_messages, user_question=message)

        self._commit_memory_background(session_id, convo, user_msg, final_msg)
        return validate_output(final_msg, state=masking_state, user_question=message)
