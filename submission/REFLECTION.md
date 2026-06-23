# Reflection — Lab 19

**Tên:** Trần Văn Khoa — MSV: 2A202600827
**Cohort:** A20-K1
**Path đã chạy:** lite (Qdrant in-memory + SQLite Feast + fastembed CPU)

---

## Câu hỏi (≤ 200 chữ)

Trên golden set 50 queries (avg Precision@10):

| Mode | exact | paraphrase | mixed | Overall |
|---|---|---|---|---|
| Keyword (BM25) | **96.7%** | 33.3% | 97.0% | 77.8% |
| Semantic (vector) | 88.7% | 24.0% | 98.5% | 73.2% |
| Hybrid (RRF k=60) | **96.7%** | 32.0% | **100%** | **78.6%** |

**Tại sao mode này thắng?**

- **exact**: BM25 thắng vì query dùng đúng từ kỹ thuật verbatim trong corpus. Hybrid tie vì BM25 signal đã đủ mạnh.
- **paraphrase**: Cả hai đều yếu vì `bge-small-en` là English-trained — semantic recall tiếng Việt paraphrase thấp (~24-33%). Trên mô hình multilingual (`bge-m3`) semantic sẽ thắng rõ hơn.
- **mixed**: Hybrid thắng tuyệt đối (100%) vì kết hợp được exact term signal (BM25) và semantic signal (vector).

**Khi nào KHÔNG dùng hybrid?**

1. **Latency budget nhỏ** (< 5ms): embedding inference ~10-20ms → dùng BM25 only.
2. **Vocabulary stable + domain-specific**: legal/medical text với exact term matching là đủ (BM25).
3. **Tài nguyên hạn chế**: embedding model nặng (~100MB+) không phù hợp edge/mobile.
4. **Corpus nhỏ** (< 1000 docs): overhead của dual-index không đáng.

---

## Điều ngạc nhiên nhất khi làm lab này

Feast online lookup P99 < 1ms (SQLite local) — nhanh hơn kỳ vọng rất nhiều. PIT join tự động loại bỏ data leakage mà không cần code thêm.

---

## Bonus challenge

- [ ] Đã làm bonus (xem `bonus/`)
- [ ] Pair work với: —
