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
            model_name = "BAAI/bge-small-en-v1.5"
            model_kwargs = {'device': 'cpu'}
            encode_kwargs = {'normalize_embeddings': True}
            _embeddings_model = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs
            )
        else:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                _embeddings_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
            except Exception:
                from langchain_core.embeddings import FakeEmbeddings
                _embeddings_model = FakeEmbeddings(size=384)
    return _embeddings_model
