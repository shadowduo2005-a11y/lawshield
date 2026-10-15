"""
Citation node – parses, verifies, formats, and appends citations to the legal draft.
"""
from __future__ import annotations

import logging
from graph.state import AgentState
from .builder import CitationBuilder
from .verifier import CitationVerifier
from .formatter import CitationFormatter
from .exporter import CitationExporter

logger = logging.getLogger(__name__)

def citation_node(state: AgentState) -> dict:
    """
    Identifies, verifies, and appends legal citations to the draft document.
    """
    logger.info("Starting Citation Engine node...")

    draft = state.get("draft_content", "")
    # Combine all historical research data to verify grounding
    research_source = "\n\n".join(state.get("research_data", []))

    # Initialize builder, verifier, and exporter
    builder = CitationBuilder()
    verifier = CitationVerifier()
    exporter = CitationExporter()

    # Step 1: Extract candidate citations from draft and research content
    candidates = builder.extract_from_text(draft + "\n" + research_source)

    verified_citations = []
    formatted_citations = []

    # Step 2: Grounding verification and formatting
    for citation in candidates:
        verify_res = verifier.verify(citation, research_source)
        
        # Keep only verified citations with reasonable confidence (e.g., > 0.5)
        if verify_res.get("verified", False) or verify_res.get("confidence", 0.0) >= 0.5:
            verified_citations.append(citation)
            
            # Format using Bluebook for cases, statutory for statutes
            if citation.volume and citation.reporter and citation.first_page:
                formatted = CitationFormatter.format_bluebook(citation)
            else:
                formatted = CitationFormatter.format_statutory(citation)
                
            formatted_citations.append(formatted)

    # Step 3: Append the Table of Authorities to the draft
    style = "bluebook" if any(c.volume for c in verified_citations) else "statutory"
    cited_draft = exporter.append_to_document(draft, verified_citations, style=style)

    logger.info("Citation node completed. Added %d verified citations.", len(verified_citations))
    return {
        "draft_content": cited_draft,
        "citations": formatted_citations
    }
