"""
cleaner.py
Text normalisation pipeline for raw text extracted from legal PDFs and DOCX files.

The raw output from PDF parsers is typically noisy — it contains:
- Null bytes and other control characters (\\x00 – \\x1F)
- Soft hyphens (\\xad) used for line-breaking
- Unicode ligatures (ﬁ, ﬂ, ﬀ, …) that don't search/compare correctly
- Form-feed page separators (\\x0c)
- Byte-order marks (\\ufeff)
- Non-breaking spaces (\\xa0, \\u202f, \\u2007) mixed with regular spaces
- Em-dashes, en-dashes used as list bullets
- Repeated blank lines from page headers/footers
- Hyphenated word-breaks at line ends (e.g., "appli-\\ncation")

This module applies a deterministic, ordered cleaning pipeline that:
1. Decodes / normalises Unicode (NFC)
2. Removes or replaces control and invisible characters
3. Fixes ligatures (for correct text search)
4. Repairs hyphenated line-breaks
5. Normalises whitespace while PRESERVING paragraph structure
6. Strips degenerate short lines that are artefacts (page numbers, headers)
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Ligature / special-character substitution table
# ---------------------------------------------------------------------------
_LIGATURE_MAP: dict[str, str] = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "st",
    "\ufb06": "st",
    "\u2019": "'",   # right single quotation mark
    "\u2018": "'",   # left single quotation mark
    "\u201c": '"',   # left double quotation mark
    "\u201d": '"',   # right double quotation mark
    "\u2013": "-",   # en dash
    "\u2014": "-",   # em dash
    "\u2022": "-",   # bullet •
    "\u2026": "...", # ellipsis
    "\u00ad": "",    # soft hyphen (invisible, used for line-breaking)
    "\ufeff": "",    # BOM
    "\u00a0": " ",   # non-breaking space
    "\u202f": " ",   # narrow no-break space
    "\u2007": " ",   # figure space
    "\u2009": " ",   # thin space
    "\u200b": "",    # zero-width space
    "\u200c": "",    # zero-width non-joiner
    "\u200d": "",    # zero-width joiner
}

# Compiled substitution regex
_LIGATURE_RE = re.compile("|".join(re.escape(k) for k in _LIGATURE_MAP))

# ---------------------------------------------------------------------------
# Control character pattern (ASCII 0x00-0x1F, excluding \t \n \r)
# ---------------------------------------------------------------------------
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Hyphenated line-break: word- followed immediately by newline then word char
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")

# Runs of blank lines (3+) collapsed to double newline (paragraph break)
_MULTI_BLANK_LINE_RE = re.compile(r"\n{3,}")

# Multiple spaces (not newlines) -> single space
_MULTI_SPACE_RE = re.compile(r"[^\S\n]+")

# Lines that are purely digits (page numbers) or 1-2 isolated non-alphanumeric
# characters are likely PDF header/footer artefacts.
# We do NOT strip lines of only punctuation like "..." to avoid over-stripping.
_ARTEFACT_LINE_RE = re.compile(r"^\s*(\d{1,4}|[\W_]{1,2})\s*$")


def clean_text(text: str, *, preserve_paragraphs: bool = True) -> str:
    """
    Apply the full cleaning pipeline to *text* extracted from a document.

    Parameters
    ----------
    text:
        Raw extracted text (may contain PDF artefacts).
    preserve_paragraphs:
        If True (default), double-newlines are kept as paragraph separators.
        If False, all newlines are collapsed to a single space (useful when
        you want a single continuous string for embedding).

    Returns
    -------
    str
        Cleaned, normalised text.
    """
    if not text:
        return ""

    # 1. Unicode NFC normalisation (compose characters)
    text = unicodedata.normalize("NFC", text)

    # 2. Replace ligatures and typographic characters
    text = _LIGATURE_RE.sub(lambda m: _LIGATURE_MAP[m.group(0)], text)

    # 3. Strip control characters (keep \t \n \r)
    text = _CONTROL_CHAR_RE.sub("", text)

    # 4. Normalise Windows line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 5. Repair hyphenated line-breaks ("appli-\ncation" -> "application")
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)

    # 6. Collapse multiple spaces on a single line (but not newlines)
    text = _MULTI_SPACE_RE.sub(" ", text)

    # 7. Drop degenerate lines (pure page numbers / single-char artefacts)
    lines = text.split("\n")
    lines = [ln for ln in lines if not _ARTEFACT_LINE_RE.match(ln)]
    text = "\n".join(lines)

    # 8. Collapse runs of 3+ blank lines to a paragraph break
    text = _MULTI_BLANK_LINE_RE.sub("\n\n", text)

    if not preserve_paragraphs:
        # Flatten to a single continuous block
        text = text.replace("\n", " ")
        text = _MULTI_SPACE_RE.sub(" ", text)

    return text.strip()


def clean_text_flat(text: str) -> str:
    """Convenience wrapper: clean and return a single-line string."""
    return clean_text(text, preserve_paragraphs=False)
