"""
tools/compare.py – Compares two legal texts and returns structured diff output.
Useful for identifying modified clauses between contract versions.
"""
from __future__ import annotations

import difflib

from langchain_core.tools import tool


@tool
def compare_documents(text_a: str, text_b: str) -> str:
    """
    Compares two text documents and returns a structured diff with a similarity score.
    Useful for comparing old vs new contract versions, legislative amendments, or clause changes.

    Returns:
      - Similarity score as a percentage
      - A unified diff showing additions (+), deletions (-), and context lines
      - A short summary of how many lines were added or removed

    Args:
        text_a: The original document text (e.g. old contract version).
        text_b: The revised document text (e.g. new contract version).
    """
    if not text_a.strip() and not text_b.strip():
        return "Error: Both documents are empty."

    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)

    # Similarity ratio (0.0 – 1.0)
    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    similarity = round(matcher.ratio() * 100, 2)

    if similarity == 100.0:
        return "✅ Documents are identical. Similarity: 100.00%"

    diff = list(difflib.unified_diff(
        lines_a,
        lines_b,
        fromfile="Document_A (Original)",
        tofile="Document_B (Revised)",
        lineterm="",
        n=2,
    ))

    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

    summary = (
        f"📊 Similarity: {similarity}% | "
        f"Lines added: {added} | Lines removed: {removed}\n"
        f"{'=' * 60}\n"
    )

    return summary + "\n".join(diff)
