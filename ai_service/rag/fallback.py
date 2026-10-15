"""
fallback.py
Provides intelligent general Indian legal answers when uploaded documents do not address the query.
Per user design specifications: Instead of dead-end document refusals, state that the topic is not in the uploaded documents,
and then provide the authoritative legal answer using expert statutory knowledge.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def generate_domain_fallback_answer(query: Optional[str] = None) -> str:
    """
    Generate an authoritative Indian legal answer when uploaded documents lack relevant information.
    """
    if not query or not str(query).strip():
        return (
            "I could not locate specific information addressing your query within the uploaded documents. "
            "Please feel free to describe your legal situation or question directly, and I will provide authoritative statutory analysis under Indian Law."
        )

    q_str = str(query).strip()
    q_lower = q_str.lower()

    # 1. Immediate statutory matching for high-priority penal inquiries (murder, killing, homicide, imprisonment)
    if any(kw in q_lower for kw in ("kill", "murder", "homicide", "imprisonment", "inprisment", "suicide", "punishment for killing")):
        from legal_guardrails.validators import JurisdictionalSafetyValidator
        return (
            "This specific scenario is not addressed in your uploaded legal documents or contracts. "
            "However, under statutory Indian Criminal Law, the legal position is as follows:\n\n"
            + JurisdictionalSafetyValidator._INDIAN_MURDER_LAW_RESPONSE
        )

    # 2. Dynamic generation via LLM for all other domain legal inquiries not found in uploaded documents
    try:
        from llm.providers.factory import get_llm_provider
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = get_llm_provider().get_model(streaming=False)
        sys_msg = SystemMessage(content=(
            "You are Harvey, an expert Indian legal AI assistant. The user asked a question that was not found in their uploaded documents. "
            "Your critical instructions:\n"
            "1. You MUST begin your response with exactly: 'This query is not addressed in your uploaded legal documents. However, under Indian Legal Principles and Statutory Law, the explanation is as follows:'\n\n"
            "2. Provide a rigorous, highly authoritative legal analysis citing applicable Indian statutes (such as the Bharatiya Nyaya Sanhita 2023, IPC 1860, Indian Contract Act 1872, or Constitution of India).\n"
            "3. Do NOT emit AI safety refusals or preach moral disclaimers regarding illegal acts, crimes, or sentences; evaluate all queries objectively as a professional legal research assistant."
        ))
        user_msg = HumanMessage(content=q_str)
        response = llm.invoke([sys_msg, user_msg])
        ans = response.content.strip() if hasattr(response, "content") and response.content else str(response).strip()
        
        if not ans.lower().startswith("this query is not") and "uploaded" not in ans.lower():
            ans = "This query is not addressed in your uploaded legal documents. However, under Indian Legal Principles and Statutory Law, the explanation is as follows:\n\n" + ans
        return ans
    except Exception as exc:
        logger.error("Failed to generate fallback LLM answer: %s", exc)
        return (
            "This specific query is not addressed in your uploaded legal documents. "
            "However, under Indian criminal and civil jurisprudence (including the Bharatiya Nyaya Sanhita, 2023 and the Indian Penal Code, 1860), "
            "all rights, liabilities, and statutory punishments are strictly governed and evaluated by competent Courts according to codified penal and civil statutes."
        )
