# Chạy song song review worker nội bộ (shadow)

Addon `edu_review_shadow` gửi video của buổi **đã có báo cáo Gemini** sang review worker nội bộ
(`services/review-worker`, máy 10.77.160.36) và lưu kết quả vào model riêng
`edu.session.review.shadow` để so sánh. Addon không ghi vào báo cáo Gemini, buổi học, điểm danh,
khóa tuần, cảnh báo thời lượng hay gợi ý học phí/lương. Gemini vẫn là nguồn chính.

Menu: *Xử lý video → So sánh worker AI* (chỉ quản lý giáo vụ).

## Quyết định đã duyệt (23/11/2026)

- Phần hỏi chuyện khởi động bằng tiếng Anh ("How are you?", "Did you go out today?") **tính là dạy**.
  Lời chào đơn thuần, chờ học sinh, kiểm tra mic/camera không tính.
- Lời văn nhận xét dự kiến dùng API chỉ nhận văn bản (transcript đã thay tên học sinh). Nhà cung cấp
  chưa chọn. Đến khi có key, worker dùng model local (`REVIEW_SYNTH_BACKEND=local`).
- Chạy shadow 1–2 tuần trước khi quyết định thay Gemini.

## Bật

1. Upgrade/cài addon trên đúng DB (`-i edu_review_shadow` lần đầu). Pause worker theo quy trình bàn giao.
2. Đặt tham số hệ thống (Settings → Technical → System Parameters):
   - `edu_review_shadow.worker_url` = `http://10.77.160.36:8090`
   - `edu_review_shadow.worker_token` = giá trị `WORKER_TOKEN` trong `E:\KimReview\app\.env.worker` trên .36
     (không ghi vào Git, chat hay log)
   - `edu_review_shadow.enabled_since` = mốc UTC `YYYY-MM-DD HH:MM:SS`; chỉ báo cáo Gemini xong sau mốc này
   - `edu_review_shadow.daily_limit` = số buổi mới mỗi ngày (mặc định 20)
3. Bật cron *GVNN: nhận xét AI song song (worker nội bộ)*. Cron cài ở trạng thái tắt.

Tắt: tắt cron. Dữ liệu đã so sánh vẫn giữ.

## Chống xử lý trùng

- Mã tác vụ = `kim-<session>-<sha256(report id, chữ ký Drive, roster, prompt)[:16]>`; mỗi báo cáo
  Gemini chỉ có một bản shadow (ràng buộc unique).
- Mọi lệnh tới worker là idempotent theo mã: tạo lại trả tác vụ cũ, upload tiếp từ offset worker đã nhận,
  `start` tác vụ đang chạy/xong không làm gì. Mất phản hồi → lần chạy sau hỏi lại worker, không gửi lại mù.
- Worker báo lỗi (`worker:...`) hoặc kết quả không qua validator → không tự chạy lại; nút
  *Tiếp tục với cùng mã tác vụ* chỉ dùng cho lỗi mạng/Drive phía Odoo.
- Cron giữ advisory lock 87426 (Gemini dùng 87425); mỗi lượt upload tối đa 240 giây rồi commit.

## Dữ liệu

- Video đi Drive → Odoo → worker trong mạng nội bộ, từng khúc 32 MB; worker kiểm tra md5.
- Worker xóa video/khung hình ngay khi xong; transcript xóa khi Odoo `ack` hoặc sau 72 giờ.
- Odoo lưu JSON kết quả (dạng báo cáo v2, học sinh theo `student_<id>`) và số đo thời gian/RAM.

## Kiểm tra

- Test addon: `--test-enable --test-tags /edu_review_shadow` trên DB thử (mock worker + Drive).
- Test worker: `python -m unittest tests.test_contract` trong `services/review-worker`.
