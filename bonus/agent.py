"""HybridMemoryAgent — episodic memory (Qdrant) + stable profile (Feast).

Design decisions:
  - Single Qdrant collection, user_id as payload filter (not per-user collections).
    Tradeoff: simpler ops vs weaker tenant isolation (see ARCHITECTURE.md §3).
  - Per-user in-memory BM25 for keyword recall (rebuilt on demand).
  - RRF k=60 fuses sparse + dense signals.
  - Feast online store (SQLite) for user profile + query velocity lookup.
  - Chunking: fixed ~100-word windows with 20-word overlap — avoids sentence
    splitter dependency (underthesea) while keeping chunks coherent enough.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, Filter, FieldCondition, MatchValue, PointStruct, VectorParams
from rank_bm25 import BM25Okapi

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
COLLECTION = "episodic_memory"
RRF_K = 60
CHUNK_WORDS = 100
CHUNK_OVERLAP = 20


def _chunk_text(text: str, chunk_words: int = CHUNK_WORDS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Fixed-size word chunking with overlap. No VN tokenizer dependency."""
    words = text.split()
    if len(words) <= chunk_words:
        return [text]
    chunks = []
    step = chunk_words - overlap
    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + chunk_words])
        chunks.append(chunk)
        if start + chunk_words >= len(words):
            break
    return chunks


class HybridMemoryAgent:
    """Minimal POC: episodic memory via Qdrant + user profile via Feast."""

    def __init__(self, feast_repo_path: Optional[Path] = None) -> None:
        self._embedder = TextEmbedding(model_name=EMBED_MODEL)
        self._qdrant = QdrantClient(":memory:")
        self._qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )
        self._point_counter = 0

        # Per-user BM25: rebuilt lazily when new docs are added.
        self._user_docs: dict[str, list[dict]] = {}   # user_id -> [{text, chunk_id}]
        self._user_bm25: dict[str, BM25Okapi] = {}    # user_id -> BM25Okapi (stale flag via _dirty)
        self._user_dirty: set[str] = set()

        # Feast (optional — graceful degrade if not materialized)
        self._feast_store = None
        if feast_repo_path is None:
            feast_repo_path = _REPO_ROOT / "app" / "feast_repo"
        if feast_repo_path.exists():
            try:
                from feast import FeatureStore
                self._feast_store = FeatureStore(repo_path=str(feast_repo_path))
            except Exception:
                pass  # no feast registry yet — degrade gracefully

    # ── write ────────────────────────────────────────────────────────────

    def remember(self, text: str, user_id: str = "u_001") -> None:
        """Chunk text, embed, upsert into Qdrant with user_id payload."""
        chunks = _chunk_text(text)
        vectors = list(self._embedder.embed(chunks))
        points = []
        for chunk, vec in zip(chunks, vectors):
            points.append(PointStruct(
                id=self._point_counter,
                vector=vec.tolist(),
                payload={"user_id": user_id, "text": chunk},
            ))
            self._user_docs.setdefault(user_id, []).append({
                "chunk_id": self._point_counter,
                "text": chunk,
            })
            self._point_counter += 1
        self._qdrant.upsert(collection_name=COLLECTION, points=points)
        self._user_dirty.add(user_id)

    # ── read ─────────────────────────────────────────────────────────────

    def _get_bm25(self, user_id: str) -> Optional[BM25Okapi]:
        if user_id not in self._user_docs:
            return None
        if user_id in self._user_dirty or user_id not in self._user_bm25:
            tokenized = [d["text"].lower().split() for d in self._user_docs[user_id]]
            self._user_bm25[user_id] = BM25Okapi(tokenized)
            self._user_dirty.discard(user_id)
        return self._user_bm25[user_id]

    def _keyword_search(self, query: str, user_id: str, top_k: int) -> list[str]:
        bm25 = self._get_bm25(user_id)
        if bm25 is None:
            return []
        user_docs = self._user_docs[user_id]
        scores = bm25.get_scores(query.lower().split())
        ranked = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]
        return [str(user_docs[i]["chunk_id"]) for i in ranked]

    def _semantic_search(self, query: str, user_id: str, top_k: int) -> list[tuple[str, str]]:
        q_vec = next(self._embedder.embed([query])).tolist()
        results = self._qdrant.query_points(
            collection_name=COLLECTION,
            query=q_vec,
            query_filter=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]),
            limit=top_k,
        )
        return [(str(p.id), p.payload["text"]) for p in results.points]

    def _get_user_profile(self, user_id: str) -> dict:
        if self._feast_store is None:
            return {}
        try:
            result = self._feast_store.get_online_features(
                features=[
                    "user_profile_features:reading_speed_wpm",
                    "user_profile_features:preferred_language",
                    "user_profile_features:topic_affinity",
                    "query_velocity_features:queries_last_hour",
                    "query_velocity_features:distinct_topics_24h",
                ],
                entity_rows=[{"user_id": user_id}],
            ).to_dict()
            return {k: v[0] for k, v in result.items()}
        except Exception:
            return {}

    def recall(self, query: str, user_id: str = "u_001", top_k: int = 3) -> str:
        """Hybrid search episodic memory + Feast profile → assembled context string."""
        depth = max(top_k * 5, 20)

        # 1. Keyword hits (BM25 on this user's docs)
        kw_ids = self._keyword_search(query, user_id, depth)

        # 2. Semantic hits (Qdrant vector search filtered by user_id)
        sem_results = self._semantic_search(query, user_id, depth)
        sem_ids = [cid for cid, _ in sem_results]
        text_by_id = {cid: txt for cid, txt in sem_results}

        # Backfill text_by_id from user_docs for BM25-only hits
        for doc in self._user_docs.get(user_id, []):
            text_by_id.setdefault(str(doc["chunk_id"]), doc["text"])

        # 3. RRF fusion
        rrf: dict[str, float] = {}
        for rank, cid in enumerate(kw_ids, start=1):
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (RRF_K + rank)
        for rank, cid in enumerate(sem_ids, start=1):
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (RRF_K + rank)

        top_ids = [cid for cid, _ in sorted(rrf.items(), key=lambda kv: -kv[1])[:top_k]]
        top_memories = [text_by_id.get(cid, "") for cid in top_ids]

        # 4. Fetch user profile from Feast
        profile = self._get_user_profile(user_id)

        # 5. Assemble context string
        parts = [f"[User profile for {user_id}]"]
        if profile:
            parts.append(
                f"  Topic affinity: {profile.get('topic_affinity', 'unknown')}"
                f" | Language: {profile.get('preferred_language', 'unknown')}"
                f" | Reading speed: {profile.get('reading_speed_wpm', '?')} wpm"
                f" | Queries last hour: {profile.get('queries_last_hour', '?')}"
                f" | Topics last 24h: {profile.get('distinct_topics_24h', '?')}"
            )
        else:
            parts.append("  (No Feast profile — using defaults)")

        parts.append(f"\n[Top-{len(top_memories)} episodic memories for query: {query!r}]")
        for i, mem in enumerate(top_memories, 1):
            snippet = mem[:200].replace("\n", " ")
            parts.append(f"  {i}. {snippet}{'...' if len(mem) > 200 else ''}")

        if not top_memories:
            parts.append("  (No memories stored yet for this user)")

        return "\n".join(parts)
