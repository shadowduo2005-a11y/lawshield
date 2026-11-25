from qdrant_client import QdrantClient
from elasticsearch import Elasticsearch
from config.settings import settings
import logging
import os

logger = logging.getLogger(__name__)

# Singletons for clients
_qdrant_client = None
_es_client = None

def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client. If external Qdrant server is unreachable, fallback to local disk Qdrant storage."""
    global _qdrant_client
    if _qdrant_client is None:
        try:
            # Try connecting to external Qdrant server first
            client = QdrantClient(url=settings.QDRANT_URL, timeout=2.0)
            client.get_collections()
            _qdrant_client = client
            logger.info("Connected to external Qdrant server at %s", settings.QDRANT_URL)
        except Exception as e:
            logger.warning(
                "External Qdrant server at %s unreachable (%s). Using local disk vector storage.",
                settings.QDRANT_URL, e
            )
            storage_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "qdrant_storage"))
            os.makedirs(storage_path, exist_ok=True)
            try:
                _qdrant_client = QdrantClient(path=storage_path)
            except Exception as lock_err:
                logger.warning("Local Qdrant file lock active (%s). Using in-memory vector storage.", lock_err)
                _qdrant_client = QdrantClient(":memory:")

    return _qdrant_client


def get_es_client() -> Elasticsearch | None:
    """Get Elasticsearch client if available; returns None if ES is unreachable."""
    global _es_client
    if _es_client is None:
        try:
            client = Elasticsearch(settings.ELASTICSEARCH_URL, request_timeout=2.0)
            if client.ping():
                _es_client = client
                logger.info("Connected to Elasticsearch at %s", settings.ELASTICSEARCH_URL)
            else:
                logger.warning("Elasticsearch ping failed at %s. ES search will be disabled.", settings.ELASTICSEARCH_URL)
                return None
        except Exception as e:
            logger.warning("Elasticsearch unreachable at %s (%s). ES search will be disabled.", settings.ELASTICSEARCH_URL, e)
            return None
    return _es_client


def init_collections(collection_name: str = "documents"):
    """Initialize collections in Qdrant and indices in ES."""
    q_client = get_qdrant_client()
    es_client = get_es_client()
    
    # Init Qdrant (384 dims for BAAI/bge-small-en-v1.5)
    try:
        from qdrant_client.http.models import VectorParams, Distance
        collections = [c.name for c in q_client.get_collections().collections]
        if collection_name not in collections:
            q_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            logger.info("Created Qdrant collection: %s", collection_name)
    except Exception as e:
        logger.error("Error initializing Qdrant collection '%s': %s", collection_name, e)

    # Init Elasticsearch index if ES is available
    if es_client is not None:
        try:
            if not es_client.indices.exists(index=collection_name):
                es_client.indices.create(
                    index=collection_name,
                    body={
                        "mappings": {
                            "properties": {
                                "text": {"type": "text"},
                                "metadata": {"type": "object"}
                            }
                        }
                    }
                )
                logger.info("Created ES index: %s", collection_name)
        except Exception as e:
            logger.error("Error initializing Elasticsearch index '%s': %s", collection_name, e)
