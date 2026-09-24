"""
R3 — Semantic Retrieval & Prototype Exemplar Bank (Bi-Encoder ONNX)

Computes dense semantic embeddings using BAAI/bge-small-en-v1.5.
Maintains positive and negative concept exemplars for prototype matching
and hard-negative mining (William Penn, Ximi Vogue, Divine Footwear, Archies, Deepam Taxi).
"""

from __future__ import annotations

import logging
from typing import Any
import numpy as np

from app.relevance.concepts import ConceptCard

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL: Any = None


def get_embedding_model() -> Any:
    """Return fastembed TextEmbedding singleton."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        try:
            from fastembed import TextEmbedding
            _EMBEDDING_MODEL = TextEmbedding("BAAI/bge-small-en-v1.5")
        except Exception as e:
            logger.warning(f"FastEmbed TextEmbedding initialization deferred: {e}")
            _EMBEDDING_MODEL = None
    return _EMBEDDING_MODEL


# In-memory default prototypes (hard-negative mined and curated positive prototypes)
_DEFAULT_PROTOTYPES: dict[str, dict[str, list[str]]] = {
    "pooja_store": {
        "positives": [
            "Sri Lakshmi Pooja Stores | pooja samagri, agarbatti, camphor, dhoop, brass diyas, kumkum",
            "Om Shakti Puja Samagri Bhandar | havan samagri, pooja items, religious books, idols",
            "Sri Venkateshwara Pooja Kendra | temple worship items, pooja thalis, garlands, kapoor",
            "Pooja Materials & Agarbathi Shop | retail pooja store selling spiritual worship goods",
        ],
        "negatives": [
            "William Penn | luxury writing instruments, premium pens, stationery accessories, notebooks",
            "Ximi Vogue | Korean fashion lifestyle store, handbags, jewelry, cosmetics, accessories",
            "Divine Footwear | footwear shop, formal shoes, leather sandals, chappals, sneakers",
            "Archies | greeting cards, gift items, photo frames, soft toys, party supplies",
            "Deepam Taxi | cab service, taxi booking, car rentals, airport taxi, passenger transport",
            "Sri Sai Restaurant | vegetarian dining, meals, south indian tiffin, dosa, coffee",
        ],
    }
}

_PROTOTYPE_EMBEDDINGS: dict[str, dict[str, np.ndarray]] = {}


def _get_prototype_embeddings(concept_id: str) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Return precomputed positive and negative embedding matrices for a concept."""
    if concept_id in _PROTOTYPE_EMBEDDINGS:
        matrices = _PROTOTYPE_EMBEDDINGS[concept_id]
        return matrices.get("pos"), matrices.get("neg")

    model = get_embedding_model()
    if not model:
        return None, None

    proto_dict = _DEFAULT_PROTOTYPES.get(concept_id, {
        "positives": [f"{concept_id} retail shop offering related products and services"],
        "negatives": ["unrelated commercial office, restaurant, medical clinic, footwear store"],
    })

    pos_texts = proto_dict.get("positives", [])
    neg_texts = proto_dict.get("negatives", [])

    try:
        pos_emb = np.array(list(model.embed(pos_texts))) if pos_texts else None
        neg_emb = np.array(list(model.embed(neg_texts))) if neg_texts else None

        _PROTOTYPE_EMBEDDINGS[concept_id] = {
            "pos": pos_emb,
            "neg": neg_emb,
        }
        return pos_emb, neg_emb
    except Exception as e:
        logger.warning(f"Error computing prototype embeddings for {concept_id}: {e}")
        return None, None


def batch_embed_texts(texts: list[str]) -> np.ndarray | None:
    """Compute dense embeddings for a list of profile texts in one batch."""
    if not texts:
        return None
    model = get_embedding_model()
    if not model:
        return None
    try:
        embs = list(model.embed(texts))
        return np.array(embs)
    except Exception as e:
        logger.warning(f"Error during batch embedding: {e}")
        return None


def compute_semantic_scores(
    profile_text: str,
    concept_id: str,
    candidate_emb: np.ndarray | None = None,
) -> tuple[float, float, float]:
    """
    Compute (sem_pos, sem_neg, sem_margin) against concept prototype bank.
    Cosine similarity in [-1, 1] mapped to [0, 1].
    """
    pos_matrix, neg_matrix = _get_prototype_embeddings(concept_id)
    if pos_matrix is None or neg_matrix is None:
        return 0.5, 0.5, 0.0

    if candidate_emb is None:
        model = get_embedding_model()
        if not model:
            return 0.5, 0.5, 0.0
        candidate_emb = np.array(list(model.embed([profile_text]))[0])

    # Normalize vectors
    c_norm = candidate_emb / (np.linalg.norm(candidate_emb) + 1e-9)
    
    # Cosine similarities
    pos_sims = np.dot(pos_matrix, c_norm) / (np.linalg.norm(pos_matrix, axis=1) + 1e-9)
    neg_sims = np.dot(neg_matrix, c_norm) / (np.linalg.norm(neg_matrix, axis=1) + 1e-9)

    max_pos = float(np.max(pos_sims))
    max_neg = float(np.max(neg_sims))

    # Map cosine similarity [-1, 1] to [0, 1]
    sem_pos = max(0.0, min(1.0, (max_pos + 1.0) / 2.0))
    sem_neg = max(0.0, min(1.0, (max_neg + 1.0) / 2.0))
    sem_margin = sem_pos - sem_neg

    return sem_pos, sem_neg, sem_margin


def add_mined_exemplar(concept_id: str, text: str, polarity: int) -> None:
    """Record a newly mined positive (+1) or negative (-1) exemplar into prototype bank."""
    if concept_id not in _DEFAULT_PROTOTYPES:
        _DEFAULT_PROTOTYPES[concept_id] = {"positives": [], "negatives": []}

    target_list = _DEFAULT_PROTOTYPES[concept_id]["positives"] if polarity > 0 else _DEFAULT_PROTOTYPES[concept_id]["negatives"]
    if text not in target_list:
        target_list.append(text)
        # Invalidate cached matrix
        if concept_id in _PROTOTYPE_EMBEDDINGS:
            del _PROTOTYPE_EMBEDDINGS[concept_id]
