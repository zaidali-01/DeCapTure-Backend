from typing import List, Tuple
from app.modules.Communications.rag.chroma_client import get_collection
from app.modules.Communications.rag.embedder import embed_text


def retrieve_relevant_chunks(
    business_id: int,
    question: str,
    top_k: int = 5,
) -> List[Tuple[str, float]]:
    """
    Query ChromaDB for the most relevant chunks to a question.
    Only searches THIS business's collection — tenant isolation guaranteed.

    Returns a list of (chunk_text, similarity_score) tuples.
    """
    collection = get_collection(business_id)

    if collection.count() == 0:
        return []

    question_vector = embed_text(question)

    results = collection.query(
        query_embeddings=[question_vector],
        n_results=min(top_k, collection.count()),
        include=["documents", "distances"],
    )

    chunks = results["documents"][0]
    distances = results["distances"][0]

    # Chroma cosine distance = 1 - similarity, so convert back
    scored = [(text, round(1 - dist, 4)) for text, dist in zip(chunks, distances)]
    return scored