# Báo cáo Benchmark và Giám sát — Ngày 14

**Họ tên:** Nguyen Trieu Duong
**Ngày chạy:** 2026-11-25 (Asia/Saigon)
**Môi trường:** Windows, Python 3.11.9, CPU AMD64, 16 CPU logic, RAM 15.2 GiB.

Phần 2–3 đo bằng máy khách Windows và agent local qua HTTP loopback. Phần 4–5
chạy container Linux thật trên Docker Desktop / Ubuntu WSL2. Toàn bộ token và
chi phí LLM do mock được cung cấp mô phỏng; không gọi API LLM trả phí.

**Trạng thái:** Đã hoàn thành benchmark local, đánh giá chất lượng, giám sát,
thí nghiệm gây lỗi và đo Locust với số replica được xác minh.

## 1. SLO của agent

| SLI | Ngưỡng sử dụng | Lý do |
|---|---|---|
| Độ trễ p95 của `/ask` | ≤ 500 ms | Ít nhất 95% phản hồi nằm trong ngưỡng độ trễ |
| Tỷ lệ lỗi `/ask` | ≤ 2% | Ngưỡng lỗi mặc định của script load test |
| Độ chính xác trên golden dataset | ≥ 80% cho baseline; 100% sau sửa KB | Giữ minh chứng trước khi sửa, sau đó yêu cầu đạt cả 23 câu |

Trong đánh giá và load test local, đặt `MOCK_ERROR_RATE=0` để tách ảnh hưởng của
độ trễ và retrieval khỏi lỗi upstream ngẫu nhiên. Vì vậy, quan sát 0% lỗi không
chứng minh hành vi ở cấu hình mặc định có 1% lỗi. `MOCK_SLOW_RATE=0.03` được dùng
cho eval và loạt đo concurrency; thí nghiệm độ trễ đuôi thay đổi riêng biến này.
Các tham số độ trễ, model và retrieval khác dùng mặc định của mã được cung cấp.
Không cố định random seed, nên kết quả khi chạy lại có thể khác.

## 2. Benchmark hiệu năng

Mỗi hàng gồm **300 request** đến agent v2 sau sửa KB. Script bỏ một request
warm-up khỏi thống kê. Các file minh chứng nằm trong `reports/` ở gốc repo.

### 2.1 Số request đồng thời và độ trễ

| Concurrency | Request/s | p50 ms | p95 ms | p99 ms | Tỷ lệ lỗi | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.12 | 200.3 | 247.0 | 1716.1 | 0% | ĐẠT |
| 10 | 37.36 | 189.9 | 239.6 | 1710.9 | 0% | ĐẠT |
| 50 | 108.41 | 195.9 | 260.3 | 1729.1 | 0% | ĐẠT |
| 100 | 42.46 | 850.0 | 4935.2 | 5293.2 | 0% | KHÔNG ĐẠT |

Nguồn: `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json` và
`load_v2_c100.json`.

Thông lượng tăng đến concurrency 50 rồi giảm ở mức 100, đồng thời độ trễ tăng.
Kết quả cho thấy có tranh chấp tài nguyên hoặc hàng đợi khi concurrency cao.
Phép đo bao gồm cả máy khách HTTP và máy chủ Windows, nên chưa xác định được
nút thắt chỉ nằm ở agent. Muốn kết luận nguyên nhân cần chạy lâu hơn, tách máy
tạo tải và đối chiếu metric phía server. Kết quả không đạt vẫn được giữ lại.

### 2.2 Độ trễ đuôi

Mỗi lần chạy gồm **300 request**, concurrency **20**.

| `MOCK_SLOW_RATE` | Trung bình ms | p95 ms | p99 ms | SLO |
|---|---|---|---|---|
| 0 | 186.8 | 229.7 | 235.3 | ĐẠT |
| 0.03 | 233.8 | 231.9 | 1685.6 | ĐẠT |
| 0.1 | 316.2 | 1686.9 | 1705.3 | KHÔNG ĐẠT |

Nguồn: `reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json` và
`load_v2_slow_0.1.json`.

Khi xác suất request chậm là 3%, p99 đã phản ánh phần đuôi chậm nhưng p95 vẫn
xấp xỉ độ trễ thông thường. Khi tăng lên 10%, p95 cũng chuyển sang vùng chậm.
Giá trị trung bình vẫn thấp hơn nhiều so với các request chậm, nên có thể che
khuất trải nghiệm của một nhóm người dùng.

## 3. Benchmark chất lượng

Đã lưu đánh giá v1/v2 ban đầu trước khi sửa KB. Không sửa golden dataset hoặc
script chấm. Ngưỡng đạt mặc định cho từng câu là **0.6** tỷ lệ từ khóa; sau sửa,
cả 23 câu đều có điểm từ khóa **1.0**.

| Chỉ số | v1 | v2 ban đầu | v2 sau sửa |
|---|---|---|---|
| Số câu đúng / tổng | 1/23 | 21/23 | 23/23 |
| Accuracy lưu trong JSON | 0.0435 | 0.9130 | 1.0000 |
| Token trung bình / câu | 57.8 | 108.8 | 118.0 |
| Tổng chi phí mock, USD | 0.000414 | 0.000757 | 0.000828 |
| Chi phí / câu đúng, USD | 0.00041355 | 0.00003607 | 0.00003599 |
| p95 ms | 201.8 | 246.9 | 249.8 |
| Cổng kiểm soát chất lượng | KHÔNG ĐẠT (≥80%) | ĐẠT (≥80%) | ĐẠT (100%, không regression) |

Nguồn: `reports/eval_v1.json`, `reports/eval_v2.json` và
`reports/eval_v2_fixed.json`. Giữ nguyên độ chính xác thập phân của từng trường
trong file: tổng chi phí được lưu ít chữ số hơn chi phí trên một câu đúng.

| Câu v2 sai ban đầu | Nội dung còn thiếu | Cách bổ sung KB |
|---|---|---|
| `security-02` | Token, thời hạn, chữ ký | Giải thích API key so với JWT, claim đã ký, `exp` và bước kiểm tra |
| `scaling-03` | CPU, memory, custom metrics | Giải thích mục tiêu HPA và cách cung cấp metric qua adapter |

Đã thêm hai mục này cho cả KB develop và production. Đánh giá HTTP cuối đạt
**23/23**, sửa được hai câu và không làm câu đã đúng trở thành sai. Retrieval
làm prompt dài hơn, tăng token, chi phí mỗi request và độ trễ; tuy nhiên, độ
chính xác tăng mạnh nên chi phí trên mỗi câu đúng giảm. Đánh giá bằng từ khóa
trên mock không chứng minh độ chính xác tổng quát của model thật.

Trong CI, có thể bật v2 với `MOCK_ERROR_RATE=0` rồi chạy `eval/run_eval.py` bằng
`--min-accuracy 1.0 --baseline <saved-baseline>`. Exit code khác 0 phải làm job
thất bại; branch protection phải yêu cầu job này thành công trước khi merge.
Baseline phải đáng tin cậy và không bị thay thế bởi chính thay đổi đang đánh giá.

## 4. Hệ thống giám sát

### 4.1 Ảnh minh chứng từ giao diện thật

- [x] [Grafana có tải](screenshots/grafana-dashboard.png), chụp khi đã xác minh đủ ba agent.
- [x] [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png).
- [x] [Trace lỗi và sự kiện exception](screenshots/jaeger-error-trace.png).
- [x] [Hai cảnh báo SLO cùng firing](screenshots/prometheus-alert-firing.png).
- [x] [Thí nghiệm instance ngừng đáp ứng riêng](screenshots/prometheus-instance-down.png).

Unit test của alert rules được cung cấp đã đạt (`promtool` thoát với mã **0**).
Metric, truy vấn, cấu hình gây lỗi và tương quan trace/log nằm trong
`reports/observability.json`. Hai trace đã chọn được giữ trong
`reports/jaeger_slow_trace.json` và `reports/jaeger_error_trace.json`.

### 4.2 Thí nghiệm gây lỗi

| Thí nghiệm | Thay đổi | Cảnh báo quan sát được | Thời gian đầu tiên thấy firing |
|---|---|---|---|
| A+B: lỗi upstream và request chậm | Đồng thời đặt `MOCK_ERROR_RATE=0.2`, `MOCK_SLOW_RATE=0.3` | `AgentHighErrorRate` | 96.1 giây |
| A+B, cùng lần chạy | Hai cấu hình trên | `AgentHighLatencyP95` | 151.3 giây |
| D: thí nghiệm khả dụng riêng | Pause một agent, sau đó unpause | `AgentInstanceDown` | 40.3 giây |

Thời gian tính từ lúc phát lệnh đổi cấu hình đến lần đầu API Prometheus trả về
trạng thái firing, được kiểm tra mỗi năm giây. Khoảng này bao gồm tạo lại
container, cập nhật DNS/scrape, cửa sổ tính rate và thời gian `for` của rule.
Thí nghiệm khả dụng chỉ dùng scraping, không tạo thêm tải người dùng; agent
đã được unpause sau đo.

Lỗi và độ chậm được đưa vào cùng lúc, nên lần chạy A+B thể hiện ảnh hưởng kết
hợp, không tách riêng tác động từng biến. Thí nghiệm pause độc lập cung cấp
kịch bản sự cố thứ hai. Cảnh báo tốc độ tiêu chi phí đã firing dưới tải baseline,
nên không gán việc firing đó cho lần gây lỗi sau.

Đổi sang v1 có thể làm chất lượng trả lời giảm trong khi metric hạ tầng vẫn
khỏe. Cần phát hiện bằng kiểm tra regression trên golden dataset trước deploy,
đánh giá mẫu câu trả lời production, kiểm tra retrieval và phản hồi người dùng.

### 4.3 Giải thích dashboard

Tại `2026-11-25T12:29:09.071603+00:00` (khoảng **19:29:09, GMT+7**), histogram
Prometheus ước lượng p95 `/ask` là **293.22 ms**, trung bình **231.75 ms**.
Khoảng chênh lệch thể hiện phần đuôi chậm. Ước lượng từ histogram khác cách
Locust tính percentile phía máy khách; không thay thế hai loại số đo cho nhau.

Ba instance lần lượt phục vụ **20.82, 20.71, 20.42 request/s**, cho thấy phân
phối tương đối đều tại thời điểm chụp. Tốc độ token input là **5004.64/s**, output
là **2723.15/s**. Input gồm chỉ dẫn hệ thống, câu hỏi và tài liệu truy xuất, nên
có thể lớn hơn output.

Request `/metrics` qua Nginx thực tế trả **404**. Prometheus scrape trực tiếp
agent trong mạng nội bộ; proxy chủ động không công khai endpoint này.

### 4.4 Điều tra bằng trace

Trace lâu nhất trong mẫu truy vấn tối đa 200 trace:

- Trace ID: `6516d868307869700fa582bd5abdd0c8`.
- Tổng thời gian: **1767.101 ms**.
- Span lá chậm nhất: **chat mock-llm-small**, **1693.959 ms**.
- Span này chiếm **95.86%** tổng thời gian; phần lớn độ trễ nằm ở bước gọi LLM,
  phù hợp với độ chậm được đưa vào mock provider.

Trace lỗi `1c8c5e410041efabfb7f4f1708aa0327` chứa sự kiện exception. Dòng log JSON
khớp trace ID được giữ nguyên từ ứng dụng:

```json
{"ts": "2026-11-25T12:19:41.698739+00:00", "level": "INFO", "service": "observable-agent", "instance": "b92708ef86de", "event": "llm_error", "trace_id": "1c8c5e410041efabfb7f4f1708aa0327", "span_id": "f582c36dd6aa622c", "request_id": "0c5130104bbe", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark mở rộng

Mỗi lần đo cuối dùng **100 người dùng**, tốc độ tăng tải **10 người dùng/giây**,
thời gian **hai phút**. Đưa tỷ lệ lỗi và tỷ lệ chậm của mock về **0.01** và
**0.03**. Bảng sử dụng **hàng `/ask`**, không gộp `/health`, từ hai CSV ở gốc repo.

| Số agent | Request/s | p50 ms | p95 ms | p99 ms | Lỗi / tổng request |
|---|---|---|---|---|---|
| 1 | 59.70 | 190 | 260 | 1700 | 70 / 7134 |
| 3 | 59.57 | 190 | 230 | 1700 | 71 / 7122 |

Nguồn: `benchmark-results/scale_1_stats.csv` và `scale_3_stats.csv`.
Locust chạy với `--no-deps` để Compose không đưa số replica về mặc định của
mẫu. Đã kiểm tra số container trước, trong và sau mỗi lần chạy. Các lần đo sai
số replica trước đó được thay bằng hai lần đo cuối đã xác minh.

Thông lượng gần như không đổi, p95 cải thiện nhẹ. Tải cố định này có thời gian
nghỉ **0.5–2 giây** giữa các thao tác, nên không buộc thông lượng tăng tuyến tính
khi thêm replica. p99 không đổi phù hợp với việc vẫn giữ cùng cơ chế giả lập
LLM chậm. Thêm replica tăng khả năng xử lý đồng thời, nhưng không loại bỏ độ trễ
provider mô phỏng. Không suy ra năng lực production từ một bài đo local ngắn.

## 6. Điều rút ra

1. Percentile ở phần đuôi thể hiện request chậm mà trung bình có thể che khuất.
2. Cảnh báo hạ tầng và đánh giá chất lượng câu trả lời phát hiện các nhóm lỗi khác nhau.
3. Retrieval có thể tăng chi phí mỗi request nhưng giảm chi phí trên mỗi câu đúng.

Khi triển khai thật, cần theo dõi thêm lỗi ở proxy, Redis, số lần bị rate limit
hoặc cost guard từ chối và chất lượng mẫu câu trả lời. Cost guard của mock chưa
phải hạn mức thanh toán tuyệt đối: request đang chạy có thể làm vượt ngân sách.
