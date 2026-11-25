"""
Memory – Vector store for past conversations using Qdrant.
"""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)

COLLECTION_NAME = "conversation_history"
VECTOR_SIZE = 384  # must match BGE small model dims (384)


def _init_collection() -> None:
    try:
        from qdrant_client.http.models import Distance, VectorParams
        from rag.retrieval import get_qdrant_client

        q_client = get_qdrant_client()
        existing = [c.name for c in q_client.get_collections().collections]
        if COLLECTION_NAME not in existing:
            q_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection: %s", COLLECTION_NAME)
    except Exception as exc:
        logger.error("Error initialising vector memory collection: %s", exc)


def save_to_vector_memory(session_id: str, messages: list["BaseMessage"]) -> None:
    """Embed and save the most-recent exchange to vector memory."""
    if not messages:
        return

    _init_collection()

    text_chunk = "\n".join(f"{m.type}: {m.content}" for m in messages[-2:])

    try:
        from qdrant_client.http.models import PointStruct
        from rag.embedding import get_embeddings
        from rag.retrieval import get_qdrant_client

        q_client = get_qdrant_client()
        vector = get_embeddings().embed_query(text_chunk)

        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={"session_id": session_id, "text": text_chunk},
        )
        q_client.upsert(collection_name=COLLECTION_NAME, points=[point])
        logger.debug("Saved exchange to vector memory for session %s", session_id)
    except Exception as exc:
        logger.error("Failed to save to vector memory: %s", exc)


def search_vector_memory(session_id: str, query: str, top_k: int = 3) -> str:
    """Return semantically related past exchanges for the given session."""
    _init_collection()

    try:
        from qdrant_client.http.models import FieldCondition, Filter, MatchValue
        from rag.embedding import get_embeddings
        from rag.retrieval import get_qdrant_client

        q_client = get_qdrant_client()
        query_vector = get_embeddings().embed_query(query)

        q_filter = Filter(
            must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))]
        )
        results = q_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=q_filter,
            limit=top_k,
        )

        chunks = [r.payload.get("text", "") for r in results.points if r.payload.get("text")]
        return "\n---\n".join(chunks)
    except Exception as exc:
        logger.error("Failed to search vector memory: %s", exc)
        return ""
