# Kim review worker (thay thế Gemini, giai đoạn thử nghiệm)

Dịch vụ CPU chạy trên VPS nội bộ cùng mạng với .128. Odoo tải video Drive như hiện tại rồi đẩy
từng phần sang worker. Worker chạy tuần tự: ffprobe → faster-whisper (timestamp) → khung hình mỗi 10 s
(độ sáng, chuyển động, OCR tên ô người tham gia) → LLM gán nhãn hoạt động từng phút và ghi chú →
LLM tổng hợp → JSON đúng `report.SCHEMA` (prompt 2.1) để Odoo chạy `validate_report()` như cũ.

Trạng thái: **chưa nối Odoo, chưa benchmark**. Gemini vẫn là phương án thay thế.

## Nguyên tắc

- LLM không tự viết mốc thời gian; nó chỉ trích mã `S<phần>.<n>` (đoạn lời nói) hoặc `W<phần>.<k>`
  (cửa sổ 60 s). Worker đổi mã sang MM:SS trong giới hạn `floor(thời lượng ffprobe)`.
- Thời gian dạy tính từ nhãn từng phút + mốc lời nói, không để LLM cộng.
- Học viên: chỉ coi là có mặt khi tên hiện trên màn hình (OCR) ≥ 2 khung. `not_observed` chỉ khi mọi phần
  đọc được tên học viên khác. Không có cảnh báo tập trung (để trống, Odoo ghi “chưa ghi nhận”).
  Không nhận dạng khuôn mặt.
- Tên học viên trong transcript được thay bằng `[student_N]` trước khi vào LLM.
- Mã tác vụ do Odoo tạo và checkpoint trước khi gửi. Mọi API idempotent; mất phản hồi thì GET lại.
- Lưu tối đa 72 giờ (`WORKER_RETENTION_HOURS`). Video/âm thanh/khung hình xóa ngay khi xong;
  transcript và kết quả xóa khi Odoo `ack` hoặc hết hạn. Log không chứa transcript, tên hay URL.

## Cài đặt trên VPS (Ubuntu/Debian, Docker)

```bash
sudo mkdir -p /opt/kimreview && sudo chown $USER /opt/kimreview
# copy thư mục services/review-worker vào /opt/kimreview
cd /opt/kimreview
cp .env.worker.example .env.worker && sed -i "s/^WORKER_TOKEN=.*/WORKER_TOKEN=$(openssl rand -hex 32)/" .env.worker
chmod 600 .env.worker
mkdir -p models/llm models/whisper
curl -L -o models/llm/Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf
docker compose build
WORKER_BIND=<IP-LAN-VPS> docker compose up -d
# chỉ mở cổng 8090 cho IP .128 (ufw allow from 10.77.160.128 to any port 8090)
```

Model Whisper tải lần đầu vào `models/whisper` (cần ghi được lần đầu; sau đó có thể mount `:ro`).

## Benchmark không cần Odoo

```bash
docker compose run --rm -v /opt/kimreview/samples:/samples worker \
  python -m review_worker bench --roster /samples/roster.json --planned 60 \
  --out /data/bench-1.json /samples/p1.mp4 /samples/p2.mp4
```

`metrics` ghi thời gian từng bước, RAM đỉnh tiến trình con và số token. So sánh `result` với báo cáo
Gemini cũ và đáp án người gán theo tiêu chí trong `docs/AI_REVIEW_PROVIDER_HANDOFF.md`.

## Test

`python tests/test_contract.py` chạy được không cần model: kiểm tra kết quả qua đúng validator Odoo,
mốc không vượt thời lượng, im lặng → chưa đủ dữ liệu, không kết luận vắng khi không đọc được màn hình,
và idempotency của mã tác vụ.
