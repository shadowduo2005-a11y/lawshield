"""
QA agent node – answers simple factual and conversational Indian legal questions directly.

This is the lightweight path for questions like:
  - "How long is the Indian Constitution?"
  - "What is habeas corpus under Indian law?"
  - "Who drafted the Indian Constitution?"
  - "What is Section 302 IPC?"
  - "What is the limitation period under the Limitation Act?"
  - "How do I file an RTI?"

Unlike the reasoning node (which runs a 3-agent document analysis pipeline),
this node gives a concise, natural conversational response — no risk
assessment format, no headers, no audit summary.
"""
from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from graph.state import AgentState
from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

_QA_SYSTEM_PROMPT = (
    "You are Harvey, a highly knowledgeable Indian legal AI assistant. "
    "Your primary jurisdiction is India. "
    "You are an expert in: the Constitution of India, IPC / Bharatiya Nyaya Sanhita (BNS), "
    "CrPC / Bharatiya Nagarik Suraksha Sanhita (BNSS), CPC, Indian Evidence Act, "
    "Transfer of Property Act, Contract Act 1872, Companies Act 2013, GST, SEBI, RBI, "
    "IT Act 2000, Consumer Protection Act, RTI Act, labour laws, family law "
    "(Hindu Marriage Act, Muslim Personal Law, Special Marriage Act), "
    "and intellectual property (Patents Act, Copyright Act, Trade Marks Act). "
    "When answering, prefer Indian statutes and Supreme Court of India / High Court judgments. "
    "Use correct Indian legal terminology (FIR, writ, petition, Magistrate, Sessions Court, etc.). "
    "Answer in a clear, helpful, and conversational tone — as an expert Indian lawyer explaining to a client. "
    "Do NOT use document-review headers like 'ANALYSIS', 'RISKS FOUND', or 'SUGGESTED CHANGES'. "
    "Keep the response concise unless the question genuinely requires a detailed explanation. "
    "For legal queries, provide a direct, clear, and authoritative answer. For greetings or casual conversation, respond in a friendly and professional manner. "
    "CRITICAL PROFESSIONAL INSTRUCTION: You are a professional Indian legal AI assistant for lawyers and citizens, NOT a child-friendly chatbot. "
    "Users will ask theoretical, hypothetical, real-world, or first-person questions about criminal liability, offenses, murder, assault, theft, penalties, and imprisonment (e.g., 'if I kill someone how long is my imprisonment'). "
    "DO NOT refuse, lecture, preach, or trigger general AI safety refusals or moralizing. "
    "Answer directly, objectively, and authoritatively citing Indian statutes—specifically the Bharatiya Nyaya Sanhita (BNS, 2023) and Indian Penal Code (IPC, 1860) (e.g., explain Section 103 BNS / Section 302 IPC for murder, which prescribes life imprisonment or death). "
    "Under NO circumstances should you EVER output United States emergency hotlines or foreign resources. If emergency help is relevant, mention ONLY Indian support numbers: Police (112), Kiran Mental Health Helpline (1800-599-0019), or Tele-MANAS (14416)."
)


def qa_node(state: AgentState) -> dict:
    """
    Answers simple Indian legal questions directly and conversationally.

    Returns a plain, natural language answer — no risk-assessment framework.
    """
    logger.info("QA node: answering factual/conversational Indian law question.")

    model = get_llm_provider().get_model()

    messages = []
    for m in state["messages"]:
        if m.type == "system":
            # Append QA specific rules to the main system prompt
            messages.append(SystemMessage(content=m.content + "\n\n" + _QA_SYSTEM_PROMPT))
        else:
            messages.append(m)

    # In case there was no system message in state
    if not any(m.type == "system" for m in messages):
        messages.insert(0, SystemMessage(content=_QA_SYSTEM_PROMPT))

    response = model.invoke(messages)
    answer = response.content

    logger.info("QA node completed (%d chars).", len(answer))
    return {
        "messages": [AIMessage(content=answer)],
    }
