"""
tools/timeline.py – Legal procedural deadline calculator.
Computes court deadlines and filing dates from a start date.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from langchain_core.tools import tool

_DATE_FORMAT = "%Y-%m-%d"


@tool
def court_timeline(start_date: str, add_days: int, label: str = "Deadline") -> str:
    """
    Calculates a legal procedural deadline by adding working days or calendar days to a start date.
    Use this to compute filing deadlines, response periods, appeal windows, or statute of limitations.

    Args:
        start_date: The base date in 'YYYY-MM-DD' format, e.g. "2024-01-15"
        add_days:   Number of calendar days to add. Use positive integers.
        label:      A descriptive label for the deadline, e.g. "Appeal Window" (default: "Deadline")

    Examples:
        court_timeline("2024-01-01", 30)           → 30-day filing deadline
        court_timeline("2024-03-15", 90, "Reply")  → 90-day reply deadline

    Returns:
        A formatted string showing the start date, deadline date, and number of days counted.
    """
    if not start_date or not start_date.strip():
        return "Error: 'start_date' cannot be empty."

    if add_days <= 0:
        return "Error: 'add_days' must be a positive integer."

    try:
        date_obj = datetime.strptime(start_date.strip(), _DATE_FORMAT)
    except ValueError:
        return f"Error: Invalid date '{start_date}'. Use YYYY-MM-DD format (e.g. '2024-01-15')."

    deadline = date_obj + timedelta(days=add_days)

    # Format output
    start_str = date_obj.strftime("%d %B %Y")
    deadline_str = deadline.strftime("%d %B %Y")
    weekday = deadline.strftime("%A")

    result = (
        f"📅 {label}\n"
        f"   Start Date : {start_str}\n"
        f"   + {add_days} calendar days\n"
        f"   Deadline   : {deadline_str} ({weekday})\n"
        f"   (Raw: {deadline.strftime(_DATE_FORMAT)})"
    )

    # Warn if deadline lands on a weekend
    if deadline.weekday() >= 5:
        result += "\n   ⚠️  Warning: Deadline falls on a weekend. Verify with local court rules."

    return result
