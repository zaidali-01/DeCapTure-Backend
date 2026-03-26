import hashlib
import math
from typing import List


DIMENSION = 384


def _normalize(vector: List[float]) -> List[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def _embed(text: str) -> List[float]:
    # Fully local deterministic embedding so ingestion works without model downloads.
    vector = [0.0] * DIMENSION
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % DIMENSION
        sign = -1.0 if digest[4] % 2 else 1.0
        weight = 1.0 + (digest[5] / 255.0)
        vector[index] += sign * weight
    return _normalize(vector)


def embed_text(text: str) -> List[float]:
    """Embed a single piece of text into a vector."""
    return _embed(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts in one batch call."""
    return [_embed(text) for text in texts]
