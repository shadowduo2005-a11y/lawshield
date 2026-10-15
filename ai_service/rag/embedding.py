from langchain_huggingface import HuggingFaceEmbeddings

# Cache the embeddings model so it is only loaded once
_embeddings_model = None

def get_embeddings():
    """Lazy load the fast, high-accuracy BGE small embedding model (384 dims)."""
    global _embeddings_model
    if _embeddings_model is None:
        model_name = "BAAI/bge-small-en-v1.5"
        model_kwargs = {'device': 'cpu'}
        encode_kwargs = {'normalize_embeddings': True}
        _embeddings_model = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
    return _embeddings_model
