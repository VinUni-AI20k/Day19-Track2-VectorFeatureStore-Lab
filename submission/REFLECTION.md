# Reflection — Lab 19

**Tên:** Lê Nguyễn Phước Thành
**Cohort:** A20-K3B
**Path đã chạy:** lite

---

## Câu hỏi (≤ 200 chữ)

> Trên golden set 50 queries, mode nào thắng ở loại query nào (`exact` /
> `paraphrase` / `mixed`), và tại sao? Khi nào bạn **không** dùng hybrid
> (i.e. khi nào pure BM25 hoặc pure vector là lựa chọn đúng)?

**`exact` (n=15) — hoà.** kw 96,7% = hyb 96,7% > sem 88,7%. BM25 đã sát trần nên RRF gần như
không còn chỗ cải thiện; kết quả là hoà, không phải hơn.

**`mixed` (n=20) — hybrid dẫn.** hyb 100,0% > sem 98,5% > kw 97,0%. Nhưng cách biệt mỏng
(1,5 điểm ≈ 3 doc/200 slot), nên là "dẫn", chưa phải "thắng chắc".

**`paraphrase` (n=15) — cả ba cùng sụp.** kw 33,3% ≈ hyb 32,0% > sem 24,0%. So với `exact`,
kw mất 63,4 điểm còn sem mất 64,7 — vector lẽ ra phải trụ được ở đây thì lại rơi ngang BM25.
Chính việc không chống chịu tốt hơn là dấu hiệu `bge-small-en-v1.5` (model tiếng Anh) không
nắm ngữ nghĩa tiếng Việt.

**Khi không dùng hybrid.** (1) Traffic chủ yếu `exact`: hybrid không cải thiện P@10 mà latency
P50 tăng 1,5 → 48,7 ms (32×) — pure BM25 mới đúng. (2) Pure vector: dữ liệu này không ủng hộ,
semantic không dẫn ở bất kỳ slice nào. Nó chỉ đúng khi embedding khớp ngôn ngữ corpus và query
dùng từ vựng khác hẳn tài liệu — điều kiện corpus này không có.

---

## Điều ngạc nhiên nhất khi làm lab này

NB3 trượt ngưỡng P99 < 50 ms (65,2 ms), và chính bảng latency bác bỏ gợi ý "RRF depth quá sâu"
mà notebook in ra: hybrid P50 48,7 ms chỉ đắt hơn semantic 46,9 ms 1,8 ms — xấp xỉ đúng chi phí
keyword (1,5 ms), nên bước hợp nhất RRF gần như miễn phí. Toàn bộ chi phí nằm ở nhánh vector;
notebook không tách riêng embed và tìm kiếm vector nên chưa kết luận được phần nào nặng hơn.

---

## Bonus challenge

- [ ] Đã làm bonus (xem `bonus/`)
- [ ] Pair work với: _<tên đồng đội nếu có>_
