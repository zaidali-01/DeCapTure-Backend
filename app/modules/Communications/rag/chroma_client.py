from functools import lru_cache


@lru_cache(maxsize=1)
def _get_client():
    try:
        import chromadb
        from chromadb.config import Settings
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "chromadb is required for document retrieval. "
            "Install project dependencies with `pip install -r requirements.txt`."
        ) from exc

    return chromadb.PersistentClient(
        path="chroma_db",
        settings=Settings(anonymized_telemetry=False),
    )


def get_collection(business_id: int):
    """Return the tenant-scoped Chroma collection for a business."""
    return _get_client().get_or_create_collection(
        name=f"business_{business_id}",
        metadata={"hnsw:space": "cosine"},
    )


def delete_document_chunks(business_id: int, document_id: int) -> None:
    """Remove only the chunks belonging to one specific document."""
    try:
        collection = get_collection(business_id)
        collection.delete(where={"document_id": document_id})
    except Exception:
        pass
