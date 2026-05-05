# Bonus: AI Memory Architecture — HybridMemoryAgent

**Contributor:** Phan Nguyen Viet Nhan (2A202600279)
**Course:** AICB-P2T2 · VinUniversity · Day 19

---

## Mô tả hệ thống

Một trợ lý AI cá nhân cho người dùng Việt Nam cần 3 lớp bộ nhớ:

| Lớp | Dữ liệu | Công nghệ | Freshness |
|---|---|---|---|
| **Episodic memory** | Hội thoại, tài liệu đã đọc, ghi chú | Qdrant (vector store) | Near-realtime (write-through) |
| **Stable user profile** | Ngôn ngữ ưu tiên, tốc độ đọc, lĩnh vực quan tâm | Feast online store (SQLite/Redis) | Daily batch refresh |
| **Recent activity** | Query 1 giờ qua, topic đã hỏi | Feast streaming feature view | Sub-minute |

---

## Sơ đồ kiến trúc

```
User query
    │
    ▼
┌───────────────────────────────────────────────────────┐
│                  HybridMemoryAgent                    │
│                                                       │
│  ┌──────────────┐    ┌──────────────────────────────┐ │
│  │ Feast Online │    │    Qdrant (in-memory/server)  │ │
│  │   Store      │    │  collection: episodic_memory  │ │
│  │              │    │  payload: {user_id, text}     │ │
│  │ user_profile │    │                               │ │
│  │ query_veloc. │    │  ┌──────────┐ ┌───────────┐  │ │
│  └──────┬───────┘    │  │ BM25     │ │ Vector    │  │ │
│         │            │  │ (per-usr)│ │ (cosine)  │  │ │
│         │            │  └────┬─────┘ └─────┬─────┘  │ │
│         │            │       │    RRF k=60  │        │ │
│         │            │       └──────┬───────┘        │ │
│         │            │         top-K results         │ │
│         │            └──────────────┬────────────────┘ │
│         │                           │                   │
│         └──────────────┬────────────┘                   │
│                        ▼                                │
│              assemble context string                    │
└───────────────────────────────────────────────────────┘
    │
    ▼
Context string → (optional) LLM → Response to user

Data flow khi user lưu memory mới:
  text → chunk (100-word windows) → embed (bge-small-en) → upsert Qdrant
                                                         → rebuild per-user BM25
```

---

## 3 Quyết định kiến trúc (với tradeoff explicit)

### 1. Chunking strategy — Fixed-size word windows (100 words, 20 overlap)

**Lựa chọn:** Chunk theo số từ cố định (100 từ), overlap 20 từ giữa các chunk.

**Đã xem xét:**
- **Per-message chunking** — 1 tin nhắn = 1 chunk: đơn giản, nhưng tin nhắn dài (>300 từ) mất thông tin ở đuôi khi embed vào 384-dim.
- **Semantic chunking** (spaCy / underthesea sentence split): chất lượng cao hơn nhưng cần dependency nặng (underthesea ~200 MB, spaCy model VN chưa ổn định 2026).
- **Fixed-size word windows** ← **chọn**: không cần NLP dependency, cross-platform, chunk size nằm trong sweet spot 50-150 từ cho `bge-small-en`. Overlap 20 từ giảm nguy cơ cắt đứt câu key.

**Tradeoff explicit:** Mất boundary tự nhiên của câu → vector của chunk có thể pha trộn 2 ý khác nhau ở ranh giới. Trong production VN thật, underthesea sentence splitter sẽ cho chất lượng tốt hơn ~15%, nhưng thêm 200 MB và thời gian init 3-5s.

**Storage cost:** 1 conversation (2000 từ) → ~20 chunks → 20 × 384 float32 = 30 KB vector data — chấp nhận được.

---

### 2. Feature schema — Tabular features, không dùng embedding features

**Lựa chọn:** Feast feature views chỉ lưu tabular features (Int64, String, Float32), không lưu embedding vector trong feature store.

**Đã xem xét:**
- **Embedding feature view** (lưu latent user preference vector từ lịch sử query): rất powerful cho personalization re-ranking, nhưng cần pipeline tính toán embedding offline (Spark job), schema evolution khi đổi model gặp vấn đề (384-dim cũ vs 768-dim mới không compatible). Re-index toàn bộ lịch sử mỗi khi đổi model là bottleneck lớn.
- **Tabular features** ← **chọn**: entity/ttl/source rõ ràng, dễ debug, dễ audit, không phụ thuộc vào embedding model version.

**Schema được chọn:**

| Feature view | Entity | TTL | Source | Lý do TTL |
|---|---|---|---|---|
| `user_profile_features` | `user_id` | 30 ngày | Parquet daily | Thói quen đọc, ngôn ngữ thay đổi chậm |
| `item_popularity_features` | `doc_id` | 24 giờ | Parquet hourly | CTR và dwell time cũ hơn 1 ngày là stale |
| `query_velocity_features` | `user_id` | 1 giờ | Streaming / Parquet | Dùng cho fraud/rate detection — cần realtime |

**Tradeoff:** Tabular không capture latent preference (ví dụ: user hay hỏi về cloud nhưng `topic_affinity` chỉ lưu 1 string). Giải pháp: periodically cập nhật `topic_affinity` bằng batch job đếm query history — đủ cho POC.

---

### 3. Freshness strategy — 3 use cases với 3 tier khác nhau

**Câu hỏi:** Khi user vừa đọc xong 1 tài liệu mới, bao lâu thì `recall()` phản ánh tài liệu đó?

| Use case | Freshness target | Cơ chế | Chi phí |
|---|---|---|---|
| **Ghi chú cá nhân** (note-taking) | **Sub-second** | Write-through vào Qdrant ngay lập tức (current design) | CPU embed ~50ms/chunk |
| **Fraud / rate detection** | **Sub-minute** | Feast streaming pipeline (Kafka → Flink → Redis) + `query_velocity_features` TTL=1h | Cần Kafka + Flink infra |
| **Stable user profile** | **Daily** | Batch Feast `materialize-incremental` chạy cron 00:00 | Rẻ nhất, phù hợp cho features ít thay đổi |

**Lý do không dùng streaming cho mọi thứ:** streaming infra (Kafka + Flink) tốn ~$500/tháng trên cloud nhỏ. Đối với stable profile (reading speed, language preference), daily batch hoàn toàn đủ. Chỉ `query_velocity_features` thực sự cần sub-minute freshness (phát hiện spam/rapid-fire queries).

**PIT join safety:** Feast `get_historical_features` đảm bảo no data leakage — feature value tại timestamp `t` không dùng dữ liệu từ sau `t`. Critical cho training pipeline để tránh training-serving skew (deck §6).

---

## Lựa chọn sai đã loại bỏ

**"Lưu episodic memory trong Feast embedding feature view"** — tôi đã cân nhắc dùng Feast `on_demand_feature_view` để embed query history vào vector rồi lưu vào feature store. Quyết định **không làm** vì:
1. Re-index cycle khác nhau: episodic memory cập nhật mỗi khi user ghi chú (có thể mỗi giây), trong khi feature store batch refresh theo giờ/ngày.
2. Feast không phải vector database — không có ANN index, `get_online_features` tra theo entity key (O(1)), không search theo similarity (O(log N) với HNSW).
3. Schema lock-in: nếu đổi embedding model (384-dim → 768-dim), phải migrate toàn bộ feature store — painful với Feast.

**Kết luận:** Episodic memory → Qdrant. Stable profile → Feast. Hai concerns tách biệt hoàn toàn, không cần hybrid của hybrid.

---

## Vietnamese-context considerations

### Code-switching (vi/en mix)
Corpus lab 19 là mixed vi/en ("Kubernetes auto-scaling cho production"). `BAAI/bge-small-en-v1.5` (English-trained) xử lý mixed text tương đối OK vì key terms kỹ thuật là tiếng Anh. Tuy nhiên, với queries hoàn toàn tiếng Việt paraphrase ("co giãn linh hoạt"), model này recall kém hơn `bge-m3` (multilingual) ~20-30%.

**Production recommendation:** Dùng `bge-m3` (Lite path ~570 MB) cho episodic memory agent tiếng Việt thật. Trade-off: 4× slower embedding (CPU), nhưng recall paraphrase VN tốt hơn đáng kể.

### Phonetic typo và VN tokenizer
Tiếng Việt có nhiều phonetic typo ("bảo mật" → "bảo mặt", "Kubernetes" → "Kubernets"). BM25 whitespace tokenizer không xử lý được typo. Options:
- `underthesea` syllable tokenizer: giảm OOV nhưng add 200 MB + init 3s.
- Whitespace ← chọn cho POC vì key technical terms (Kubernetes, RAG, OAuth) ít typo hơn common words.

### Privacy / Decree 13 (VN data protection)
Episodic memory lưu nội dung cá nhân → phải cân nhắc:
- Per-user collection (isolation tốt hơn) vs single collection + payload filter (ops đơn giản hơn). POC dùng payload filter — production nên dùng per-user collection để xoá toàn bộ data khi user request right-to-erasure.
- Encryption at rest: SQLite Feast store và Qdrant data không encrypt by default → production cần disk encryption.

---

## Honest limitations (What this POC doesn't handle)

1. **Privacy isolation:** Single Qdrant collection với payload filter — nếu filter bug, user A có thể thấy memory của user B. Production: per-user collection.
2. **CRUD on memories:** Không có `forget(memory_id)` — user không thể xoá ký ức cụ thể.
3. **Memory decay / TTL:** Qdrant không tự xoá memory cũ → storage tăng vô hạn. Cần job định kỳ prune memories > 90 ngày chưa được recall.
4. **Multi-device sync:** In-memory Qdrant mất data khi restart. Production: Qdrant server với persistent volume.
5. **Concurrency:** BM25 per-user rebuild là blocking — với 1000+ users đồng thời, cần index update strategy (incremental BM25 hoặc ElasticSearch).
6. **LLM integration:** `recall()` chỉ trả context string — không gọi LLM thật. Full agent cần thêm LLM call với retrieved context.

---

## Vibe-coding log (tùy chọn)

**Prompt hiệu quả nhất:** "Given this spec: chunk text into ~100-word windows with 20-word overlap, no NLP dependency, return list[str]. Include edge case when text < chunk_size." → AI generate `_chunk_text()` đúng ngay lần đầu, chỉ cần review off-by-one ở điều kiện `break`.

**Prompt fail:** "Design the feature schema for a Vietnamese AI assistant." → AI trả về generic schema không liên quan VN context, không có TTL rationale. Phải re-prompt với explicit constraint: "TTL cho query_velocity phải < 1 giờ vì dùng cho fraud detection, explain why daily batch không đủ."

**Lesson:** Specify constraints và tradeoff trong prompt, không chỉ spec "what". AI tốt cho mechanical code (chunking, RRF loop), kém cho judgment decisions (TTL choice, isolation strategy).
