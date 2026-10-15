"""
rag/citation/generator.py — anti-hallucination hardened citation generator.

Changes vs previous version:
- Truncate each source document to 2 000 chars (was unlimited) before sending
  to the LLM to ensure the model can actually see the text it must cite.
- After the LLM appends citations, validate that every [Doc N] reference in
  the output corresponds to a real document in the provided list. Strip any
  orphan [Doc N] references (where N > len(documents)) so the LLM cannot
  fabricate citations to documents that do not exist.
- Wrapped in try/except: on any failure, return the original generation
  unchanged rather than raising.
"""
from __future__ import annotations

import logging
import re

from langchain_core.messages import HumanMessage
from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

# Maximum characters per document sent to the citation LLM
_MAX_DOC_CHARS = 2000


def _strip_orphan_doc_refs(text: str, num_docs: int) -> str:
    """Remove [Doc N] references where N > num_docs (hallucinated citations).

    E.g., if there are 3 documents, [Doc 4] and [Doc 99] are stripped.
    Valid references [Doc 1] through [Doc N] are kept untouched.
    """
    def _replace(match: re.Match) -> str:
        n = int(match.group(1))
        if 1 <= n <= num_docs:
            return match.group(0)  # valid reference — keep
        logger.warning(
            "Citation generator produced orphan reference %s (only %d docs available) — stripping.",
            match.group(0),
            num_docs,
        )
        return ""  # hallucinated reference — strip

    return re.sub(r"\[Doc\s+(\d+)\]", _replace, text)


def generate_citations(generation: str, documents: list[str]) -> str:
    """Append a Citations section to *generation*, linking claims to source docs.

    Validates all [Doc N] references in the LLM output and strips any that
    refer to non-existent documents to prevent hallucinated citations.
    """
    if not documents:
        return generation

    model = get_llm_provider().get_model()

    # Truncate each doc to _MAX_DOC_CHARS so the model can actually read them
    context = "\n---\n".join(
        f"[Doc {i + 1}]: {doc[:_MAX_DOC_CHARS]}" for i, doc in enumerate(documents)
    )

    prompt = f"""You are a citation agent for a legal AI system.
Review the following answer and the source documents.
Append a 'Citations' section to the END of the answer linking ONLY claims that are
explicitly present in the source documents to their specific [Doc X] reference.
Rules:
- Only reference [Doc 1] through [Doc {len(documents)}] — these are the ONLY valid document numbers.
- Do NOT invent, infer, or fabricate any [Doc N] that is not in the list above.
- Do NOT change the original answer text; only append the Citations section.
- If a claim is not supported by any document, do not cite it.

Source Documents:
{context}

Answer:
{generation}
"""
    try:
        response = model.invoke([HumanMessage(content=prompt)])
        cited_output = response.content

        # Post-generation validation: strip any [Doc N] where N > len(documents)
        validated_output = _strip_orphan_doc_refs(cited_output, len(documents))

        return validated_output
    except Exception as exc:
        logger.warning("Citation generation failed (%s); returning original answer.", exc)
        return generation
