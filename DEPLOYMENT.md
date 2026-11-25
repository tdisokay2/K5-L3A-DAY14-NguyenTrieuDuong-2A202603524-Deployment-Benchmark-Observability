# Thông tin triển khai

**Nền tảng:** Railway
**URL public:** https://agent-production-a59969e8.up.railway.app
**Dashboard project:** https://railway.com/project/360fffa4-6721-42fe-8175-40a876815f51
**Observability:** https://railway.com/project/360fffa4-6721-42fe-8175-40a876815f51/observability?environmentId=bab3d470-c68f-4554-88b8-534fe87d8660
**Thời điểm kiểm tra public:** 19:31:44 ngày 25/11/2026, GMT+7 (minh chứng gốc ghi UTC).

Agent và Redis được triển khai trong cùng project. Nguồn triển khai là ứng dụng
hoàn chỉnh ở `06-lab-complete/`, tải trực tiếp bằng Railway CLI từ thư mục staging
riêng. Không cần và không thực hiện commit/push. Dịch vụ đã được gọi qua HTTPS
public, không chỉ được kiểm tra trên localhost.

## Kết quả kiểm tra public

| Request | Xác thực | Mã thực tế |
|---|---|---|
| `GET /health` | Không cần | 200 |
| `GET /ready` | Không cần | 200 |
| `POST /ask` | Thiếu API key | 401 |
| `POST /ask` | API key hợp lệ | 200 |

Minh chứng response đã bỏ thông tin xác thực:
[deployment_checks.json](reports/deployment_checks.json).
Ảnh dịch vụ public: [running.png](screenshots/running.png).
Ảnh Swagger với kết quả health/readiness và request không có key:
[test.png](screenshots/test.png). Kết quả request có key được ghi trong JSON,
không kèm key đã gửi.

Ảnh [dashboard.png](screenshots/dashboard.png) thể hiện project `day14-agent`,
môi trường `production`, agent và Redis đều Online. Các bảng Variables đóng,
không hiển thị thông tin xác thực.

## Đối chiếu project Railway

Đã kiểm tra bằng CLI trong đúng project
`360fffa4-6721-42fe-8175-40a876815f51`, environment
`bab3d470-c68f-4554-88b8-534fe87d8660` ngày 25/11/2026:

| Dịch vụ | Trạng thái deployment | Bị dừng |
|---|---|---|
| `agent` | `SUCCESS` | Không |
| `Redis` | `SUCCESS` | Không |

Trang Observability yêu cầu phiên đăng nhập web. Trình duyệt riêng của trợ lý
hiện Login/404, nên các trạng thái trên được xác minh bằng CLI đã xác thực,
không phải suy đoán từ biểu đồ trên trang. Đây không phải kết luận rằng trang
bị lỗi khi chủ tài khoản truy cập.

## Các biến môi trường đã đặt trên Railway

| Biến | Cấu hình |
|---|---|
| `PORT` | `8000`, khớp cổng đích của domain public |
| `ENVIRONMENT` | `production` |
| `AGENT_API_KEY` | Giá trị ngẫu nhiên riêng, chỉ lưu trong biến dịch vụ Railway |
| `REDIS_URL` | Tham chiếu biến `REDIS_URL` riêng của dịch vụ Redis |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1` |
| `MONTHLY_BUDGET_USD` | `10` |
| `LOG_LEVEL` | `INFO` |

Repository không chứa giá trị API key hoặc chuỗi kết nối Redis riêng. Ngân sách
LLM là chi phí mô phỏng, không phải hóa đơn tài nguyên Railway. Giữ dịch vụ hoạt
động đến khi được chấm; theo dõi mức sử dụng trial trên dashboard và xóa project
sau khi chấm nếu không còn cần.

## Chạy lại bốn phép kiểm tra trong Ubuntu

Lấy API key riêng từ Railway và nhập ở lời nhắc ẩn; không ghi key vào lệnh hoặc
báo cáo được chia sẻ:

```bash
BASE='https://agent-production-a59969e8.up.railway.app'
read -rsp 'Nhap AGENT_API_KEY da deploy: ' AGENT_API_KEY; echo
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
unset AGENT_API_KEY
```

Chuỗi mã mong đợi và đã quan sát: **200, 200, 401, 200**.
