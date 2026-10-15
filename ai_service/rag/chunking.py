from __future__ import annotations

import re
import uuid
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Regular expression to match common legal section & clause headings
# e.g., "Clause 10 — ARTIFICIAL INTELLIGENCE SYSTEMS", "10. ARTIFICIAL INTELLIGENCE SYSTEMS",
# "Section 5: Confidentiality", "ARTICLE IV: NON-COMPETE"
_HEADING_PATTERN = re.compile(
    r"(?m)^[ \t]*("
    r"(?:Clause|Section|ARTICLE|Article|CLAUSE|SECTION)[ \t]+(?:\d+|[A-Z]+|\d+\.\d+)[ \t\:\.\-\—\–]+[^\n]+"
    r"|(?:\d+|\d+\.\d+)\.[ \t]+[A-Z0-9][A-Za-z0-9 \t\:\-\—\–\(\)]{2,80}"
    r")[ \t]*$",
    re.MULTILINE,
)

# Extract section number and title from heading string
_SECTION_NUM_RE = re.compile(r"(?i)(?:Clause|Section|Article)?\s*(\d+|[A-Z]+|\d+\.\d+)")


def _extract_section_meta(heading: str) -> tuple[str, str]:
    heading_clean = heading.strip()
    match = _SECTION_NUM_RE.search(heading_clean)
    num = match.group(1) if match else ""
    return num, heading_clean


def get_text_splitter(chunk_size: int = 1200, chunk_overlap: int = 200) -> RecursiveCharacterTextSplitter:
    """Returns a pre-configured character splitter for large clauses."""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", "; ", ". ", " ", ""],
    )


def chunk_text(text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
    """Heading-aware legal document chunker.

    Preserves semantic legal clauses intact with their clause headers and numbers,
    attaches section header prefixes to child sub-chunks if a clause is large,
    and assigns section metadata (section_number, section_title, chunk_id, neighbor IDs).
    """
    if not metadata:
        metadata = {}

    doc_name = metadata.get("filename") or metadata.get("title") or metadata.get("document_name") or "document.txt"
    base_meta = {k: v for k, v in metadata.items() if k not in ("chunk_id", "section_number", "section_title")}

    # Find heading positions in text
    headings = list(_HEADING_PATTERN.finditer(text))

    sections: List[dict] = []
    if headings:
        # Preamble / text before first heading
        first_start = headings[0].start()
        if first_start > 0:
            preamble = text[:first_start].strip()
            if preamble:
                sections.append({
                    "title": "Preamble",
                    "number": "0",
                    "content": preamble,
                })

        for i, match in enumerate(headings):
            title = match.group(1).strip()
            num, title_clean = _extract_section_meta(title)
            start_pos = match.start()
            end_pos = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            content = text[start_pos:end_pos].strip()
            sections.append({
                "title": title_clean,
                "number": num,
                "content": content,
            })
    else:
        # Fallback: treat entire document as one section
        sections.append({
            "title": "General",
            "number": "1",
            "content": text.strip(),
        })

    raw_chunks: List[dict] = []
    splitter = get_text_splitter()

    for sec in sections:
        sec_title = sec["title"]
        sec_num = sec["number"]
        sec_content = sec["content"]

        if len(sec_content) <= 1400:
            raw_chunks.append({
                "text": sec_content,
                "section_title": sec_title,
                "section_number": sec_num,
            })
        else:
            # Sub-split large clause and prefix each child chunk with the section title
            sub_docs = splitter.split_text(sec_content)
            for idx, sub_txt in enumerate(sub_docs):
                prefix = f"[{sec_title} (Cont.)]" if idx > 0 else f"[{sec_title}]"
                full_chunk_text = f"{prefix}\n{sub_txt}" if not sub_txt.startswith(sec_title) else sub_txt
                raw_chunks.append({
                    "text": full_chunk_text,
                    "section_title": sec_title,
                    "section_number": sec_num,
                })

    # Assign IDs and neighboring chunk linkages
    chunk_ids = [str(uuid.uuid4()) for _ in raw_chunks]
    documents: List[Document] = []

    for idx, c in enumerate(raw_chunks):
        cid = chunk_ids[idx]
        prev_id = chunk_ids[idx - 1] if idx > 0 else None
        next_id = chunk_ids[idx + 1] if idx + 1 < len(chunk_ids) else None

        chunk_metadata = {
            **base_meta,
            "chunk_id": cid,
            "chunk_index": idx,
            "section_number": c["section_number"],
            "section_title": c["section_title"],
            "document_name": doc_name,
            "prev_chunk_id": prev_id,
            "next_chunk_id": next_id,
        }

        documents.append(Document(page_content=c["text"], metadata=chunk_metadata))

    return documents

