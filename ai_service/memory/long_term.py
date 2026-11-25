"""
Memory – Long-Term Fact Store.

Facts are extracted from each completed exchange and stored in a PostgreSQL database
using the LongTermFact table created by Prisma.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
import psycopg2
from typing import Dict, List

from langchain_core.messages import HumanMessage

from llm.providers.factory import get_llm_provider
from config.settings import settings

logger = logging.getLogger(__name__)

_MAX_FACTS = 25  # cap per session to avoid prompt bloat

def _get_connection():
    if not settings.DATABASE_URL:
        raise ValueError("DATABASE_URL is not set")
    return psycopg2.connect(settings.DATABASE_URL)

def extract_and_save_facts(session_id: str, exchange: str) -> None:
    """
    Extract facts from the given exchange using an LLM,
    and save them directly to the LongTermFact PostgreSQL table.
    """
    if not settings.DATABASE_URL:
        logger.warning("DATABASE_URL is not set, skipping long-term memory save.")
        return

    model = get_llm_provider().get_model()

    prompt = f"""Extract any core, long-term personal facts or preferences from this exchange.
Return ONLY valid JSON as a list of strings. If there are no long-term facts to extract, return an empty list [].

Exchange:
{exchange}
"""

    try:
        response = model.invoke([HumanMessage(content=prompt)])
        raw = response.content

        # Parse JSON array safely
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            facts: List[str] = json.loads(match.group())
        else:
            cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
            facts = json.loads(cleaned)

        if not isinstance(facts, list):
            logger.warning("Extracted facts were not a list: %r", facts)
            return

        # Filter out non-strings
        new_facts = [f for f in facts if isinstance(f, str)]
        if not new_facts:
            return

        with _get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Fetch existing facts to prevent exact duplicates
                cur.execute('SELECT content FROM "LongTermFact" WHERE "threadId" = %s', (session_id,))
                existing_facts = {row[0] for row in cur.fetchall()}

                inserted = 0
                for fact in new_facts:
                    if fact not in existing_facts:
                        fact_id = str(uuid.uuid4())
                        cur.execute(
                            'INSERT INTO "LongTermFact" (id, "threadId", content, "createdAt") VALUES (%s, %s, %s, NOW())',
                            (fact_id, session_id, fact)
                        )
                        inserted += 1

                # 2. Enforce the maximum fact limit (keep newest)
                cur.execute('SELECT id FROM "LongTermFact" WHERE "threadId" = %s ORDER BY "createdAt" ASC', (session_id,))
                rows = cur.fetchall()
                if len(rows) > _MAX_FACTS:
                    excess = len(rows) - _MAX_FACTS
                    ids_to_delete = [r[0] for r in rows[:excess]]
                    cur.execute('DELETE FROM "LongTermFact" WHERE id = ANY(%s)', (ids_to_delete,))
            
            conn.commit()

        logger.debug("Inserted %d new long-term facts for session %s", inserted, session_id)

    except Exception as exc:
        logger.warning("Failed to extract or save long-term facts: %s", exc)


def get_long_term_facts(session_id: str) -> str:
    """Return a formatted string of facts from the database for injection into the system prompt."""
    if not settings.DATABASE_URL:
        return ""

    facts = []
    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT content FROM "LongTermFact" WHERE "threadId" = %s ORDER BY "createdAt" ASC', (session_id,))
                rows = cur.fetchall()
                facts = [r[0] for r in rows]
    except Exception as exc:
        logger.warning("Failed to fetch long_term_facts from db: %s", exc)
        return ""

    if not facts:
        return ""
    
    lines = "\n".join(f"- {f}" for f in facts)
    return f"Long-term facts about this user:\n{lines}"
