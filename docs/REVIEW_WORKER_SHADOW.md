# Kim Worker: review worker nội bộ (chính thức, so sánh, Gemini dự phòng)

Addon `edu_review_shadow` gửi video buổi học sang review worker nội bộ (`services/review-worker`, máy
10.77.160.36), lưu kết quả vào model riêng `edu.session.review.shadow`. Từ 23/11/2026 Kim Worker là nguồn
**chính** cho buổi chưa có nhận xét (mục *Ưu tiên Kim Worker*), Gemini là dự phòng. Với buổi đã có báo cáo
Gemini, worker chỉ chạy để so sánh và không ghi vào báo cáo Gemini, buổi học, điểm danh, khóa tuần, cảnh báo
thời lượng hay gợi ý học phí/lương.

Menu: *Xử lý video → So sánh worker AI* (chỉ quản lý giáo vụ).

## Quyết định đã duyệt (23/11/2026)

- Phần hỏi chuyện khởi động bằng tiếng Anh ("How are you?", "Did you go out today?") **tính là dạy**.
  Lời chào đơn thuần, chờ học sinh, kiểm tra mic/camera không tính.
- Lời văn nhận xét và điểm rubric dùng **Gemini text Free Tier** (người dùng chọn 23/11/2026), một lần gọi
  mỗi buổi: `SYNTH_REDUCE_BACKEND=gemini`, `GEMINI_MODEL=gemini-3.5-flash` (bucket quota khác model video
  production). Free Tier có thể dùng dữ liệu để huấn luyện, nên chỉ gửi transcript đã thay tên học sinh, kể cả
  tên ASR viết gần giống ("Ellie" ~ ELLY); không gửi video/âm thanh/khung hình/ID Odoo.
- Nhãn hoạt động, mốc bắt đầu/kết thúc và thời gian dạy vẫn tính trên VPS (model local + quy tắc).
- Key nằm ở `GEMINI_API_KEY` trong `E:\KimReview\app\.env.worker` (bản sao key Free Tier đang lưu ở cấu hình
  Gemini production). Đổi key trong Odoo thì phải cập nhật file này. Không ghi vào Git, chat hay log.
- Chốt điểm cố định: tiêu chí > 2.0 cần ít nhất 2 dẫn chứng hợp lệ, nếu không giới hạn ở 2.0.
- Chạy shadow 1–2 tuần trước khi quyết định thay Gemini.

Benchmark 23/11/2026 (worker / Gemini video): buổi 42 điểm 8.0/6.5, dạy 28.1/28.1 phút; buổi 187 điểm 7.5/8.4,
dạy 51.7/32.2 phút (Gemini bỏ sót đoạn sau 19:30); buổi 27 điểm 7.5/7.0, dạy 54.0/53.8 phút. Mốc bắt đầu lệch
≤ 6 giây. Lời gọi Gemini text mỗi buổi khoảng 8 giây, 7–10 nghìn token vào. Điểm giữa hai lần chạy dao động
khoảng ±0.5 nên chỉ đánh giá lệch điểm trên nhiều buổi.

## Trạng thái production

Đã cài và bật trên .128/kimacademy ngày 23/11/2026: `enabled_since` = `2026-11-23 01:21:49` (UTC),
`daily_limit` = 20, cron 5 phút đang chạy. Backup trước cài: `C:\KimAcademy\backups\review-shadow-prod-20261123`.

## Báo cáo chính thức cho buổi chưa có nhận xét (từ 23/11/2026)

Người dùng duyệt: buổi đã dạy, có Drive, **chưa có báo cáo done** (chưa có báo cáo hoặc chỉ có báo cáo lỗi,
kể cả 24 buổi Gemini mất phản hồi) được chạy bằng worker và tạo **một báo cáo AI mới** `model_name =
kim-worker/<model>`. Báo cáo này dùng cho buổi học, cảnh báo thiếu thời lượng, gợi ý học phí/lương và trang
giáo viên như báo cáo Gemini. Báo cáo lỗi cũ giữ nguyên (không reset `analysis_started`).

- Xếp hàng: `env['edu.session.review.shadow']._queue_official()` (idempotent theo mã tác vụ, cũ nhất trước).
  Ngày 23/11 đã xếp 61 buổi (26/10–18/11).
- Tuần tự: chỉ một buổi nằm trên worker; buổi sau chỉ upload khi không còn dòng `waiting`.
- Chỉ tạo báo cáo khi lúc đó buổi vẫn chưa có báo cáo done, không có lượt Gemini đang chạy, Drive/học viên/
  thời lượng lịch không đổi, tuần chưa khóa và không đang giữ khóa tuần tự Gemini (87425, 0). Ngược lại kết quả
  chỉ ở dòng worker với lỗi `not_published:<lý do>`.
- Chế độ so sánh không lấy báo cáo `kim-worker/*` làm báo cáo Gemini.

## Ưu tiên Kim Worker, Gemini dự phòng (17.0.1.2.0)

Bật bằng tham số `edu_review_shadow.prefer_worker_since` = mốc UTC `YYYY-MM-DD HH:MM:SS` (để trống = tắt, quay về
Gemini tự xếp hàng như cũ). Khi bật:

- Thêm/sửa link Drive **không** tự tạo lượt Gemini. Cron worker (5 phút) tự xếp mọi buổi đã dạy, có Drive, chưa có
  báo cáo done, tuần chưa khóa.
- Lượt Gemini tự xếp **trước mốc**, chưa tới inference (`analysis_started`, batch, provider response, result đều trống)
  và không phải *Phân tích ngay* được hủy (`cancelled`, dọn file tạm, ghi chú "Đã chuyển sang Kim Worker") đúng lúc
  buổi vào hàng worker, trong khóa tuần tự Gemini (87425, 0). Không lấy được khóa thì để lượt sau.
- Lượt Gemini đã gửi inference, *Phân tích ngay*, hoặc tạo sau mốc (bấm tay/dự phòng) giữ buổi ở Gemini: worker không
  nhận buổi đó. Nếu worker đã xong mà buổi còn lượt Gemini mở, worker **chờ** (`publish_wait:gemini_in_progress`,
  thử lại 15 phút); Gemini xong trước thì `not_published:already_reviewed`, Gemini lỗi thì báo cáo worker được lưu.
- Nút **Phân tích** trên buổi đã dạy chưa có nhận xét gửi buổi cho worker và đưa lên đầu hàng (`priority`). *Phân tích
  ngay* (chọn model Gemini), *Phân tích lại* buổi đã có nhận xét, buổi chưa xác nhận dạy, hoặc video worker đã kết thúc
  lỗi vẫn dùng Gemini. Trang Nhận xét AI của buổi hiện dòng trạng thái Kim Worker (vị trí hàng đợi/bước/lỗi).
- Dòng worker lỗi (`failed`, kể cả Drive/transport sau 6 lần) hoặc kết quả không dùng được
  (`not_published:parts_mismatch`, `not_published:create_*`) được xét dự phòng **một lần**: tạo một lượt Gemini mới
  (`fallback_note=gemini_queued`) trừ khi buổi đã có báo cáo done, đang có lượt Gemini mở, có dòng worker mới hơn,
  Gemini tắt, hoặc từng có lượt Gemini **mất phản hồi** (`unknown_gemini_attempt`, không tạo lượt mới theo quy tắc).
- Thứ tự chạy: bấm tay → báo cáo chính thức → so sánh; vẫn chỉ một buổi trên worker.

## Hạn mức Gemini Free Tier (worker, từ 25/11/2026, addon 17.0.1.3.0)

Sự cố 23–25/11: hạn mức ngày của `gemini-3.5-flash` Free Tier chỉ đủ khoảng 15–18 buổi; sau đó mọi buổi lỗi
`worker:LLMError:gemini_http_429` sau 3 lần chạy (khoảng 45 phút mỗi buổi) và bị chuyển sang Gemini video dự phòng.
Người dùng duyệt phương án A + B2 và dọn dữ liệu:

- Worker (`.env.worker`): `GEMINI_FALLBACK_MODELS=gemini-3.5-flash-lite` (hạn mức riêng), `GEMINI_QUOTA_RESET_UTC_HOUR=8`.
  Lỗi 429 *theo ngày* (đọc `quotaId ...PerDay` trong phản hồi, không log nội dung) chặn model đó đến 08:05 UTC
  (15:05 VN) và chuyển sang model sau; 429 *theo phút* chờ ngắn rồi thử lại. Hết mọi model: job **không lỗi**, quay
  lại hàng đợi với `stage=quota_wait`, giữ chép lời/khung hình đã tính, không tính lượt chạy; runner nghỉ tới giờ
  reset. Trạng thái hạn mức lưu ở `E:\KimReview\data\gemini-quota.json`. Model đã viết nhận xét ghi trong
  `llm_usage.reduce_model` → `model_name = kim-worker/<model>` để so chất lượng flash và flash-lite.
- Odoo: dòng worker lỗi chỉ vì hạn mức (`gemini_http_429`/`gemini_quota`) **không** dự phòng sang Gemini
  (`fallback_note=quota_requeue`); cron tự tạo lượt worker mới với mã tác vụ mới (`make_official_key(..., rerun=n)`,
  worker không bao giờ chạy lại mã đã lỗi), dòng cũ ghi `requeued`. Lượt Gemini dự phòng chưa gửi của dòng đó bị hủy
  trong khóa 87425 (`requeued:gemini_cancelled`); lượt Gemini đã gửi/đang chạy giữ nguyên và buổi ở lại Gemini.
- Trang Nhận xét AI hiện "đang chờ hạn mức Gemini miễn phí của ngày mới (khoảng 15:00)" khi job ở `quota_wait`;
  nút *Phân tích* trên buổi lỗi hạn mức đưa buổi lại worker (ưu tiên), không gọi Gemini.
- Truy cập: .36 chỉ mở cổng 22/8090 cho .128; SSH tới .36 qua .128 (ProxyCommand). Backup worker trước khi thay:
  `E:\KimReview\backups\worker-quota-20261125`.

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
