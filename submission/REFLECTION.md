# Reflection — Lab 19

**Tên:** Phan Nguyen Viet Nhan
**Cohort:** A20-K1
**Path đã chạy:** lite

---

## Câu hỏi (≤ 200 chữ)

> Trên golden set 50 queries, mode nào thắng ở loại query nào (`exact` /
> `paraphrase` / `mixed`), và tại sao? Khi nào bạn **không** dùng hybrid
> (i.e. khi nào pure BM25 hoặc pure vector là lựa chọn đúng)?

Trên golden set: **keyword (BM25)** thắng với `exact` queries vì các từ kỹ
thuật ("Kubernetes", "OAuth", "PostgreSQL") xuất hiện verbatim trong corpus —
BM25 IDF cho term hiếm điểm cao. **Semantic (vector)** ưu thế hơn với
`paraphrase` queries nhưng bị giới hạn bởi `bge-small-en` (English-only) khi
gặp tiếng Việt thuần. **Hybrid (RRF k=60)** thắng toàn diện trên `mixed`
queries vì kết hợp được tín hiệu exact-term từ BM25 và semantic từ vector.

Không dùng hybrid khi: (1) corpus nhỏ (<1000 docs) và queries hoàn toàn exact
— BM25 đủ, overhead RRF không đáng; (2) latency budget cực kỳ chặt (<5ms) và
corpus đã được chuẩn hoá tốt; (3) domain rất narrow với vocabulary kiểm soát
được — pure vector với model fine-tuned trên domain đó thường thắng hybrid.

---

## Điều ngạc nhiên nhất khi làm lab này

Embedding model `bge-small-en-v1.5` (English-trained) vẫn hoạt động tương đối
tốt với mixed vi/en corpus vì key technical terms là tiếng Anh. Nhưng trên
pure Vietnamese paraphrase queries, recall giảm rõ rệt — đây là teaching moment
về tầm quan trọng của việc chọn multilingual model (bge-m3) cho production VN.

---

## Bonus challenge

- [x] Đã làm bonus (xem `bonus/`)
- [x] Pair work với: SOLO
