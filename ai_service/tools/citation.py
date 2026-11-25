"""
tools/citation.py – Formats legal citations into standard formats.
Supports Bluebook (US) and Indian Legal Citation styles.
"""
from __future__ import annotations

from langchain_core.tools import tool


@tool
def format_citation(
    case_name: str,
    volume: str,
    reporter: str,
    first_page: str,
    year: str,
    style: str = "bluebook",
) -> str:
    """
    Formats a legal case citation into a standard format.

    Supports two citation styles:
      - 'bluebook'  (US) → Case Name, Volume Reporter Page (Year)
      - 'indian'         → Case Name (Year) Volume Reporter Page

    Args:
        case_name:  Full name of the case, e.g. "Smith v. Jones"
        volume:     Volume number of the reporter, e.g. "123"
        reporter:   Reporter abbreviation, e.g. "F.3d" or "SCC"
        first_page: First page of the case in the reporter, e.g. "456"
        year:       Year of the decision, e.g. "2010"
        style:      Citation style: "bluebook" (default) or "indian"

    Examples:
        format_citation("Smith v. Jones", "123", "F.3d", "456", "2010")
        → "Smith v. Jones, 123 F.3d 456 (2010)"

        format_citation("State of Maharashtra v. Mayer Hans George", "1965", "SCR", "123", "1964", "indian")
        → "State of Maharashtra v. Mayer Hans George (1964) 1965 SCR 123"
    """
    # Validate inputs
    for field_name, field_val in [
        ("case_name", case_name),
        ("volume", volume),
        ("reporter", reporter),
        ("first_page", first_page),
        ("year", year),
    ]:
        if not field_val or not str(field_val).strip():
            return f"Error: '{field_name}' cannot be empty."

    style = style.lower().strip()
    if style == "indian":
        return f"{case_name.strip()} ({year.strip()}) {volume.strip()} {reporter.strip()} {first_page.strip()}"
    if style == "bluebook":
        return f"{case_name.strip()}, {volume.strip()} {reporter.strip()} {first_page.strip()} ({year.strip()})"

    return f"Error: Unknown citation style '{style}'. Use 'bluebook' or 'indian'."
