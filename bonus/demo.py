"""5-query demo for HybridMemoryAgent.

Run: conda run -n AI_20K python bonus/demo.py
Expected: exits 0, prints assembled context for each of 5 queries.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bonus.agent import HybridMemoryAgent

SEPARATOR = "=" * 70


def section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def main() -> None:
    print("Initialising HybridMemoryAgent (loading embedding model)...")
    agent = HybridMemoryAgent()

    # ── Seed episodic memory ──────────────────────────────────────────────
    # Simulate a user who has read several tech documents.
    memories = [
        ("Kubernetes auto-scaling cho phép cluster tự động tăng số lượng Pod "
         "khi CPU vượt ngưỡng. HPA (Horizontal Pod Autoscaler) dùng metrics-server "
         "để lấy CPU/memory rồi điều chỉnh replicas. VPA (Vertical Pod Autoscaler) "
         "tăng resource request của Pod. Cluster Autoscaler thêm Node mới khi Pod "
         "pending do thiếu tài nguyên. Đây là nền tảng để triển khai ứng dụng "
         "cloud-native trên AWS EKS, GKE, Azure AKS."),

        ("Zero-trust security model yêu cầu xác thực và uỷ quyền cho mọi request, "
         "kể cả trong mạng nội bộ. Nguyên tắc: never trust, always verify. "
         "Triển khai với mTLS giữa các service, OAuth 2.0 + JWT cho người dùng, "
         "network policy Kubernetes để giới hạn traffic giữa namespace. "
         "Kết hợp với WAF và intrusion detection tạo thành defense-in-depth."),

        ("RAG (Retrieval-Augmented Generation) kết hợp vector search với LLM. "
         "Bước 1: embed câu hỏi người dùng thành dense vector. "
         "Bước 2: tìm top-K documents liên quan trong vector store (Qdrant, Weaviate). "
         "Bước 3: nhét documents vào context window của LLM. "
         "Bước 4: LLM sinh câu trả lời có căn cứ. "
         "Hybrid search (BM25 + vector + RRF) tăng Recall@10 từ 78% lên 91%."),

        ("Feature store giải quyết training-serving skew bằng Point-in-Time join. "
         "Feast là open-source feature store: offline store (Parquet/BigQuery) cho training, "
         "online store (Redis/SQLite) cho serving < 10ms. "
         "TTL phải chọn theo business: query_velocity TTL=1h để phát hiện fraud real-time, "
         "user_profile TTL=30d vì thói quen thay đổi chậm."),

        ("Tôi đang nghiên cứu về tự động mở rộng hạ tầng đám mây. "
         "Hôm nay đọc về spot instance trên AWS: giá rẻ hơn 70-90% so với on-demand "
         "nhưng có thể bị thu hồi trong 2 phút. Chiến lược: dùng spot cho stateless workload "
         "(batch job, worker), on-demand cho control plane và stateful service."),
    ]

    print("\nSeeding 5 memories for user u_001...")
    for i, mem in enumerate(memories, 1):
        agent.remember(mem, user_id="u_001")
        print(f"  [{i}/5] stored ({len(mem.split())} words)")

    # ── 5 demo queries ────────────────────────────────────────────────────

    # Query 1: Simple vector hit — specific topic in episodic memory
    section("Query 1 — Simple recall (vector hit): Kubernetes")
    ctx = agent.recall("Tôi đã đọc gì về Kubernetes?", user_id="u_001")
    print(ctx)

    # Query 2: Profile-dependent recommendation (needs topic_affinity)
    section("Query 2 — Profile-aware: Recommend đọc gì tiếp")
    ctx = agent.recall("Recommend cho tôi đọc gì tiếp theo", user_id="u_001")
    print(ctx)

    # Query 3: Fresh activity signal (needs queries_last_hour)
    section("Query 3 — Recent activity: Tôi đang quan tâm gì gần đây?")
    ctx = agent.recall("Tôi đang quan tâm đến chủ đề gì gần đây?", user_id="u_001")
    print(ctx)

    # Query 4: Paraphrase (vector wins — no exact term overlap)
    section("Query 4 — Paraphrase (vector wins): hạ tầng tự co giãn")
    ctx = agent.recall("Tài liệu về tự động mở rộng hạ tầng theo lưu lượng?", user_id="u_001")
    print(ctx)

    # Query 5: Mixed hybrid + profile — cross-topic retrieval
    section("Query 5 — Mixed hybrid + profile: cloud security summary")
    ctx = agent.recall("Cho tôi summary về cloud security và bảo vệ hạ tầng", user_id="u_001")
    print(ctx)

    print(f"\n{SEPARATOR}")
    print("  Demo complete — all 5 queries executed successfully.")
    print(SEPARATOR)


if __name__ == "__main__":
    main()
