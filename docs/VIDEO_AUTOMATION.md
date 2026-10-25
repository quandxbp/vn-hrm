# Video buổi học: Google Drive → YouTube

## Trạng thái — 24/10/2026

- Module `edu_video` **17.0.1.2.0**, phụ thuộc `edu_gvnn` **17.0.1.1.1**, chạy Odoo 17. Đã nâng cấp DB local `gvnn`, chưa deploy Internet.
- **Xử lý nền và tự xếp hàng đang tắt. Chưa upload video thật.**
- Kênh đích: **AU KIM NGAN @YUYONG90**. Người dùng chỉ được mời quản lý qua Studio, không đủ quyền API cho kênh này. Chủ sở hữu thực sự cần cấp OAuth sau deploy.
- Drive và YouTube có kết nối/token riêng. Drive có thể dùng email của người dùng, YouTube dùng chủ kênh.
- Client OAuth đã nhập DB local từ JSON người dùng cung cấp. Không đưa JSON/Client Secret/token vào Git/chat/log. `client_secret*.json` được gitignore. Backup DB chứa secrets, cần giữ riêng.

## Sử dụng

1. Quản trị hệ thống mở **GVNN → Cấu hình → Kết nối dịch vụ → Google Drive / YouTube**.
2. Nhập file JSON OAuth nếu chưa có. Lưu trước khi bấm **Nhập cấu hình JSON**.
3. **Kết nối Google Drive** bằng email có quyền tải các file video được chia sẻ.
4. **Kết nối / đổi kênh YouTube** bằng tài khoản chủ kênh. Kiểm tra tên, handle và Channel ID. Trường kênh cần kết nối đang là `@YUYONG90`; Google trả kênh khác thì bị từ chối trước khi lưu token.
5. Bật **Cho phép xử lý video nền**. Chỉ bật được khi cả hai kết nối và kênh đích hợp lệ.
6. Tùy nhu cầu bật **Tự xếp hàng khi nhập link Drive**. Chỉ các lần tạo/lưu link sau đó được xếp hàng; không quét và đăng toàn bộ video cũ.
7. Trong **Buổi học → Video buổi học**, nhập link Drive rồi lưu. Có nút **Đẩy lên YouTube** để xếp hàng thủ công kể cả khi chưa kết nối; yêu cầu chỉ chạy khi xử lý nền được bật và kết nối hợp lệ.
8. Xem tiến độ/lỗi trong tab Video hoặc **GVNN → Lịch học → Video buổi học**. List buổi học có cột tùy chọn **Video YouTube**. Tải lại màn hình để xem trạng thái mới.

Upload mặc định **Không công khai (unlisted)**, không thông báo người đăng ký. Tiêu đề tự tạo theo ngày, giáo viên và giờ học; không tự đưa tên học viên vào mô tả. Khi Google trả ID video, hệ thống điền `youtube_url`. YouTube có thể cần thêm thời gian xử lý sau upload.

## Lỗi và tiếp tục

- Trạng thái: Chờ xử lý → Đang tải Drive → Đang gửi YouTube → Đã tải lên. Có Lỗi, Cần kiểm tra YouTube và Đã hủy.
- Lỗi mạng/HTTP 429/5xx thử lại tối đa 3 lần với thời gian chờ tăng dần. **Thử lại** tiếp tục phiên upload đã lưu, không tạo bản mới.
- Lưu URL resumable trước khi gửi byte video. Khi tiếp tục, hỏi tiến độ Google; nếu lần cuối đã thành công nhưng phản hồi mất, lấy lại cùng ID video.
- Phiên hết hạn hoặc không xác định kết quả chuyển **Cần kiểm tra YouTube**, không tự tạo phiên khác.
- Nếu video đã có: nhập link vào buổi học và hủy yêu cầu lỗi. Nếu chắc chắn chưa có: dùng **Tạo phiên mới sau kiểm tra**, đọc xác nhận trước khi tiếp tục. Có thể tạo trùng nếu kiểm tra thiếu.
- **Hủy xử lý** dừng tại Odoo, dọn cache; không xóa video trên YouTube. Nếu cron đang gửi một phần, thử lại thao tác sau khoảng một phút.
- Không thay link Drive khi yêu cầu cũ còn hoạt động/lỗi chưa giải quyết. Không ghi đè link YouTube đã nhập tay. Không tự sửa `video_posted` hoặc link recording cũ. Hai trường legacy không còn hiển thị trên form; link YouTube cũ được chuyển sang trường YouTube khi nâng cấp `edu_gvnn` 17.0.1.4.1, giữ bản gốc để tương thích Excel.
- Upload nền chỉ điền trường YouTube kể cả sau chốt lương; không sửa dữ liệu tài chính. Sửa thủ công vẫn theo quy tắc khóa lương hiện có.

## Tải Drive và lưu trữ

- Link HTTPS file trên `drive.google.com/file/d/...`, `open?id=...`, `uc?id=...`; không nhận thư mục hoặc host tùy ý. Có hỗ trợ `resourcekey`, Shared Drives.
- Kiểm tra `capabilities.canDownload`, MIME video, dung lượng, MD5 và ổ đĩa trước upload. File của người khác được nếu tài khoản kết nối có quyền tải.
- Mặc định giới hạn **10 GB/video**, chỉnh trong cấu hình (1–256 GB).
- Tải/gửi theo phần 8 MiB, không nạp cả video vào RAM. Cache trong `<Odoo data_dir>/edu_video/<hash_database>/<job_id>.video`, nằm trong volume Odoo hiện có.
- Cache xóa khi thành công/hủy; lỗi giữ cache để tiếp tục. Hủy những yêu cầu lỗi không cần nữa để giải phóng đĩa. Giữ volume data_dir khi restart/deploy.
- Cron mỗi phút, xử lý một job tối đa khoảng 45 giây giữa các request. Request có timeout riêng. PostgreSQL advisory lock ngăn hai cron gửi cùng job; commit checkpoint sau mỗi phần.

## Deploy Internet

1. Backup DB/filestore. Cài `edu_gvnn` trước, rồi `-i edu_video` nếu chưa installed; nếu đã có thì `-u edu_gvnn,edu_video`. Restart web sau nâng cấp.
2. Đặt Odoo sau reverse proxy HTTPS trên domain thật, cấu hình proxy/cookie và DB filter đúng DB. Giữ data_dir volume và cron bật (`max_cron_threads >= 1`), cấp đủ timeout cron tải video. Local hiện dùng `limit_time_real_cron = -1`.
3. Google Cloud: bật **Google Drive API** và **YouTube Data API v3**.
4. OAuth client **Web application**: thêm Authorized redirect URI chính xác:

   ```text
   https://TEN-MIEN-ODOO/edu-video/google/callback
   ```

5. Trong Odoo, đổi **Redirect URI** thành cùng địa chỉ và lưu. Không còn hardcode localhost. Nếu nhập lại JSON, tải bản JSON mới có redirect đó. Không cần tạo client mới chỉ vì đổi domain.
6. Nếu OAuth còn Testing, thêm email tải Drive và email chủ kênh vào **Audience → Test users**. Refresh token Testing của các scope này hết hạn sau 7 ngày; cần hoàn thiện trạng thái ứng dụng trước vận hành lâu dài.
7. Chủ kênh mở Odoo ở domain trên, dùng phiên Odoo có quyền quản trị để bấm kết nối YouTube và tự đăng nhập Google. Quyền được mời qua **YouTube Studio → Quyền** không hỗ trợ API cho kênh được mời. Không yêu cầu chia sẻ mật khẩu Google.
8. Xác nhận đúng **@YUYONG90**, kết nối Drive. Bật xử lý nền, thử một video trước, kiểm tra đúng kênh và unlisted; sau đó bật tự xếp hàng nếu muốn.

DB mới không có OAuth client/token local: nhập JSON trên server qua cấu hình. Nếu restore DB local, vẫn nên kết nối lại trên domain thật. Callback kiểm tra phiên Odoo, user/DB, nonce một lần và hạn 10 phút.

## Kiểm tra

**23 tests mocked đạt** trên bản sao DB, không gọi Google thật: OAuth, tách token/scope, handle, URL/callback, tự xếp hàng/chống trùng, Drive, checksum, unlisted, mất mạng, tiếp tục offset, phục hồi kết quả cuối, phiên hết hạn, tạo lại sau kiểm tra, quyền và cập nhật link sau chốt lương.

Chưa kiểm chứng upload thực tế vì người dùng chọn kết nối chủ kênh sau deploy. DB kiểm tra không dùng token thật và được xóa sau hoàn tất.

Backup trước nâng cấp local: `D:\Projects\vn-hrm-backups\video-automation-20261024\gvnn.dump`.

## Tài liệu chính thức

- [Drive downloads](https://developers.google.com/workspace/drive/api/guides/manage-downloads)
- [YouTube resumable uploads](https://developers.google.com/youtube/data/guides/using_resumable_upload_protocol)
- [YouTube videos.insert](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert)
- [Quyền được mời và giới hạn API](https://support.google.com/youtube/answer/9481328?hl=vi)
- [OAuth web server](https://developers.google.com/identity/protocols/oauth2/web-server)
