# Bàn giao — 27/10/2026

## Cập nhật 28/10/2026 — tối ưu upload

- `edu_video` **17.0.1.7.0**: cấu hình ngôn ngữ âm thanh/metadata, thumbnail JPEG 1280×720
  với logo + giáo viên + tuần + ngày/phần, playlist riêng theo giáo viên/kênh.
- Cron sau upload xử lý ảnh bìa/playlist riêng, lỗi không làm mất link hoặc upload lại video.
  Nút retry riêng, lưu kết quả từng bước, dò lại playlist/item trước khi tạo lại sau mất mạng.
- OAuth thêm youtube.force-ssl. Kết nối cũ cần người dùng kết nối lại YouTube/cấp quyền;
  không tự mở consent hoặc chỉnh quyền thật. Chưa có scope vẫn giữ upload/thumbnail hoạt động.
- Không tự tối ưu video đã upload trước lần nâng cấp. Các tùy chọn bật mặc định cho upload mới.
- Xem VIDEO_AUTOMATION.md để vận hành. Source nằm trong commit bàn giao trên
  `feature/edu-gvnn`; chưa deploy production.
- 57 tests edu_video đạt trên DB clone; thumbnail JPEG đã kiểm tra trực quan.
  Đã backup DB + filestore và nâng cấp module local trên `kimacademy`, `gvnn`.
  Ba job đã upload trong bản sao production vẫn Không xếp hàng, không gọi Google thật.
- Buổi học / Video buổi học: tên tiếng Anh nổi bật trên tên Việt; thứ tự ngày trong
  tuần mặc định MON → SUN, giữ thứ tự giờ giảm dần như trước. Đã kiểm tra trên local `kimacademy`.

## Cập nhật 28/10/2026 — mẫu mô tả giới thiệu

- `edu_video` **17.0.1.6.2** áp dụng mẫu cũ đã được người dùng chọn: dòng lịch ở đầu,
  giới thiệu học tiếng Anh trực tuyến, thông tin giáo viên/tuần/ngày/giờ, website và 3 hashtag.
- Lấy dữ liệu thực tế từ buổi học; không tự suy luận chủ đề, không thêm tên học sinh vào mô tả.
- Đã chạy hai kiểm tra logic mô tả (mẫu, MR/MS, ngày/giờ, thiếu tuần/giờ) và restart web local.
  Chưa deploy production; không sửa video đã đăng hoặc metadata của phiên upload đã mở.

## Metadata upload mới

- Source `edu_video` **17.0.1.6.1**: description rút gọn một dòng theo mẫu
  `20:30–21:00 Thứ Hai 26/10/2026` (giờ Việt Nam).
- `status.privacyStatus=public`, `status.selfDeclaredMadeForKids=false` trong videos.insert.
  XML config_default cập nhật singleton hiện có sang public khi upgrade, giữ nguyên OAuth/token.
- Job lưu description để xem, refresh trước upload cùng title; resumable đang chạy giữ metadata cũ.
- API không hỗ trợ bật/tắt bình luận. Đã thêm hướng dẫn trên màn hình cấu hình và VIDEO_AUTOMATION.md:
  Studio → Cài đặt → Kiểm duyệt cộng đồng → Kiểm soát nội dung → bật bình luận video mới → Lưu.
- Source được bàn giao trong commit kèm tài liệu này trên `feature/edu-gvnn`.
  Chưa deploy hoặc thay cài đặt kênh/video thật.
- **45 tests edu_video đạt**, 0 lỗi trên DB clone (`artifacts/video-metadata-tests.log`),
  gồm payload Công khai/không dành cho trẻ em, description ngày/thứ/giờ,
  giờ qua nửa đêm, queued refresh và giữ metadata của phiên resumable đang chạy.

## Tiêu đề YouTube

- Từ `edu_video` **17.0.1.5.0**, gồm cả tính năng dọn cache 7 ngày bên dưới.
- Format `KIMENGLISH - MS HOPE - Kelly & Lily (WEEK 102)`; đa phần thêm `(1)`, `(2)`...
  MR/MS lấy từ teaching_title; tên học sinh ưu tiên name_en rồi name_vi, nối bằng &.
- Title helper dùng lúc tạo job và tính lại trước metadata/upload để xử lý job cũ đang chờ
  và trường hợp thêm Phần 2 sau khi xếp hàng Phần 1. Phiên đã có upload_url giữ nguyên title.
- Thiếu danh xưng/tuần/học sinh hoặc title vi phạm giới hạn100/ký tự <> sẽ dừng trước API upload,
  báo lỗi cho người dùng bổ sung; không suy đoán hoặc tự cắt mất thông tin.
- **44 tests edu_video đạt** (12 cache, 6 title và upload/OAuth cũ), gồm đúng ví dụ người dùng,
  MR một học sinh, fallback tên Việt, đánh vắng không bỏ tên, hai phần, queued refresh/resume,
  kiểm tra payload thực sự gửi vào videos.insert qua mock.
- Chưa upload/đổi tiêu đề video thật. Chưa deploy. DB test đã dọn.

## Dọn video tạm sau 7 ngày

- Source `edu_video` **17.0.1.4.0** bổ sung cron
  **GVNN: dọn video tạm quá hạn 7 ngày**, chạy mỗi 15 phút, mặc định Active.
- `cache_started_at` đánh dấu lúc bắt đầu tải; không gia hạn theo mtime khi tải tiếp.
  Job cũ chưa có mốc này dùng `create_date`, file mồ côi dùng mtime.
- Chỉ xóa `<job_id>.video` trong thư mục cache của DB hiện tại, không quét filestore,
  DB khác hoặc đi theo symlink. Không gọi Google để xóa Drive/YouTube.
- Cùng advisory lock với worker. File đang được xử lý bỏ qua lượt quét đó;
  worker chặn dùng cache quá hạn ở bước xử lý tiếp theo.
- Job còn dang dở chuyển cancelled; nếu đã có resumable upload URL thì chuyển uncertain,
  giữ thông tin phiên để người quản lý kiểm tra YouTube trước khi đăng lại.
  Job done giữ nguyên trạng thái và link.
- Ghi trạng thái dừng vào DB trước khi xóa file để tránh retry tự động trên file đã mất.
  Nếu xóa bị từ chối, ghi warning, thử ở cron sau và không cho reset tuổi cache qua retry.
- Retry sau dọn tải lại từ đầu; phiên upload chưa rõ kết quả cần thao tác restart đã kiểm tra.
- **38 tests edu_video đạt**, gồm 12 test dọn cache và các test upload/OAuth cũ.
  Tests chỉ dùng file giả trong thư mục tạm và DB clone; không tải/upload/xóa video thật.
- DB test đã xóa; DB chính local không được nâng cấp trong task này.
  Docker local được mở để chạy test; không bật web local.

**Chưa có hiệu lực trên kimacademy.uk:** cần deploy source, backup DB/filestore,
upgrade `edu_video`, restart Odoo và kiểm tra scheduled action Active/cron workers bật.
Toàn bộ thay đổi source, tests và ghi chú nằm trong commit kèm tài liệu này.

## Google production

- Đã lưu callback `https://kimacademy.uk/edu-video/google/callback` và xác nhận Drive
  kết nối thành công trong thao tác trình duyệt trước đó.
- Sau đó người dùng tự cấu hình lại tài khoản Google khác, báo đã hoàn tất và đang thử
  video khoảng 150 MB ở trạng thái Đang tải Drive. Chưa xác minh upload thật hoàn tất.
- Không ghi Client Secret, token hay nội dung JSON OAuth vào Git/log/tài liệu.
