import logging

logger = logging.getLogger(__name__)

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    HuggingFaceEmbeddings = None

# Cache the embeddings model so it is only loaded once
_embeddings_model = None

def get_embeddings():
    """Lazy load the embedding model."""
    global _embeddings_model
    if _embeddings_model is None:
        if HuggingFaceEmbeddings is not None:
            try:
                model_name = "BAAI/bge-small-en-v1.5"
                model_kwargs = {'device': 'cpu'}
                encode_kwargs = {'normalize_embeddings': True}
                _embeddings_model = HuggingFaceEmbeddings(
                    model_name=model_name,
                    model_kwargs=model_kwargs,
                    encode_kwargs=encode_kwargs
                )
                return _embeddings_model
            except Exception as exc:
                logger.warning("Failed to initialize HuggingFaceEmbeddings: %s", exc)

        try:
            from config.settings import settings
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            # Note: langchain-google-genai expects "text-embedding-004", NOT "models/text-embedding-004"
            _embeddings_model = GoogleGenerativeAIEmbeddings(
                model="text-embedding-004",
                google_api_key=settings.GEMINI_API_KEY
            )
        except Exception as exc:
            logger.warning("Failed to initialize GoogleGenerativeAIEmbeddings: %s; using FakeEmbeddings", exc)
            from langchain_core.embeddings import FakeEmbeddings
            _embeddings_model = FakeEmbeddings(size=384)
    return _embeddings_model

