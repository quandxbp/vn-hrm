# Video buổi học: Google Drive → YouTube

## Ngôn ngữ, ảnh bìa và playlist — 28/10/2026

Cập nhật `17.0.1.8.0`: ảnh bìa được dựng trực tiếp ở **3840×2160**, tên giáo viên và tuần
được làm lớn, crop lề trong suốt của logo trước khi thu nhỏ, JPEG không giảm mẫu màu và
giữ dưới 2 MB. Không phóng to lại ảnh 1280×720 đã lưu; đổi bìa video cũ cần tạo lại ảnh
và cập nhật riêng sau khi người quản lý đồng ý.

Lỗi mạng, 429/5xx và 404 ở bước tối ưu được thử lại tối đa 3 lần sau 2/4/8 phút.
Mỗi bước giữ dấu đã thành công, tra lại video trong playlist trước khi thêm, giữ ID playlist
để không tạo playlist mới khi tài nguyên chưa sẵn sàng. Lịch thử lại hiện trong chi tiết job.
Job cũ đang lỗi không tự được xếp lại khi nâng module.

Từ `edu_video` **17.0.1.7.0**:

- Cấu hình ngôn ngữ âm thanh (mặc định tiếng Anh) và ngôn ngữ tiêu đề/mô tả
  (mặc định tiếng Việt), gửi qua `defaultAudioLanguage` và `defaultLanguage` lúc upload.
  Đổi cho đúng ngôn ngữ thực tế; không tự tạo phụ đề hoặc dịch âm thanh.
- Mặc định bật tự tạo thumbnail JPEG (3840×2160 từ bản 1.8), gồm logo Kim Academy, giáo viên,
  tuần, ngày và số phần nếu có nhiều đoạn. Dùng Pillow + font DejaVu Sans/Arial.
  Ảnh được lưu trong chi tiết job để xem lại. Không nén lại hoặc thay đổi video gốc.
- Mặc định tự tạo/reuse playlist `KIMENGLISH - MR/MS TÊN GIÁO VIÊN` trên đúng kênh.
  Playlist mới theo chế độ hiển thị đang cấu hình; các đoạn cùng buổi được xếp cạnh nhau.
  Lưu ID playlist vào job, dùng lại giữa các buổi và khi đổi tên giáo viên.
- Xử lý ảnh bìa/playlist bằng cron riêng mỗi 2 phút, chỉ khi xử lý nền được bật,
  chỉ cho job vừa upload xong. Job cũ được đánh dấu Không xếp hàng, không tự sửa video cũ.
  Video đã upload giữ trạng thái/link ngay cả khi ảnh bìa hoặc playlist lỗi.
- Trong **Xử lý Drive → YouTube**, xem trạng thái Ảnh bìa / Playlist và lỗi chi tiết.
  Nút **Thử lại ảnh bìa / playlist** chỉ làm hai bước này, không gửi lại video.
  Bước đã thành công được bỏ qua; trước khi thêm lại kiểm tra video đã nằm trong playlist chưa.
  Khi tạo playlist mất phản hồi, giữ dấu chưa xác nhận và yêu cầu kiểm tra trước khi thử lại.

**Kết nối YouTube cũ cần cấp quyền lại:** OAuth mới yêu cầu thêm `youtube.force-ssl`
để tạo/sửa playlist. Bấm **Kết nối / đổi kênh YouTube** và chọn đúng kênh, chấp thuận quyền.
Không cần kết nối lại Drive. Chưa có quyền playlist vẫn upload và đặt thumbnail được,
nhưng job báo cần kết nối lại cho bước playlist. Kênh phải có quyền dùng custom thumbnails;
nếu YouTube từ chối ảnh, job giữ lỗi để xử lý sau. Có thể tắt riêng từng tính năng ở cấu hình.

API tham khảo: [ngôn ngữ](https://developers.google.com/youtube/data/reference/rest/v3/videos),
[ảnh bìa](https://developers.google.com/youtube/data/reference/rest/v3/thumbnails/set),
[tạo playlist](https://developers.google.com/youtube/data/reference/rest/v3/playlists/insert),
[xếp video](https://developers.google.com/youtube/data/reference/rest/v3/playlistItems/insert).

## Thông tin và hiển thị upload — 27/10/2026

Từ `edu_video` **17.0.1.6.0**, upload mới đặt **Công khai** và
**Không, nội dung này không dành cho trẻ em**. Thay thế mặc định unlisted cũ.
Từ **17.0.1.6.2**, mô tả giữ lịch Việt Nam ở dòng đầu và bổ sung mẫu giới thiệu:

```text
20:30–21:00 Thứ Hai 26/10/2026

Buổi học tiếng Anh trực tuyến cùng MS HOPE tại Kim Academy — tuần 103.
Video ghi lại buổi học để học viên xem lại và ôn tập.

THÔNG TIN BUỔI HỌC
• Giáo viên: MS HOPE
• Tuần học: 103
• Ngày học: Thứ Hai, 26/10/2026
• Giờ học: 20:30–21:00 (giờ Việt Nam)

KHÁM PHÁ KIM ACADEMY
Thông tin chương trình học: https://kimacademy.uk/

#KimAcademy #HocTiengAnh #TiengAnhOnline

--------------------------------------
► FOLLOW KIM ACADEMY OFFICIAL:
YouTube: https://www.youtube.com/@YURYONG90
Facebook: https://www.facebook.com/mskim.kimacademy
Email: kimacademy.edu@gmail.com

© Bản quyền thuộc về Kim Academy Official ☞ Do not Reup
© Copyright by Kim Academy Official ☞ Do not Reup
```

Từ **17.0.1.6.3**, cuối mô tả bổ sung khối FOLLOW và bản quyền theo nội dung người dùng cung cấp.

Giáo viên/danh xưng, số tuần, ngày và giờ lấy từ buổi học thực tế.
Không tự thêm chủ đề bài học, trình độ hoặc tên học sinh vào mô tả.

Mô tả được xem trong chi tiết job; tính lại cùng tiêu đề trước khi bắt đầu upload.
Phiên resumable đã mở giữ metadata đã gửi. Video đã đăng không tự thay đổi.
Nâng cấp module sẽ chuyển cấu hình hiện có sang public; không thay OAuth/token.

**Bình luận:** API upload không có thuộc tính bật/tắt bình luận.
Chủ kênh cần vào **YouTube Studio → Cài đặt → Kiểm duyệt cộng đồng → Kiểm soát nội dung**,
bật bình luận về video mới rồi **Lưu**. Không đặt kênh/video là dành cho trẻ em
nếu muốn cho phép bình luận. Odoo không thể bảo đảm bình luận bật nếu YouTube hạn chế video.

Tham khảo: [videos.insert](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert),
[cài đặt bình luận của kênh](https://support.google.com/youtube/answer/16622701?hl=vi&co=GENIE.Platform%3DDesktop).

## Tiêu đề upload — 27/10/2026

Từ `edu_video` **17.0.1.5.0**, tiêu đề tự tạo theo mẫu:

```text
KIMENGLISH - MS HOPE - Kelly & Lily (WEEK 102)
KIMENGLISH - MS HOPE - Kelly & Lily (WEEK 102) (1)
KIMENGLISH - MS HOPE - Kelly & Lily (WEEK 102) (2)
```

- Danh xưng Thầy/Cô trong hồ sơ giáo viên tương ứng MR/MS; tên giáo viên in hoa.
- Ưu tiên tên tiếng Anh học sinh, nếu trống dùng tên tiếng Việt; hiển thị dạng Kelly/Lily,
  nối bằng ` & `. Lấy danh sách học sinh của buổi, kể cả học sinh được đánh vắng.
  Buổi không có học viên liên kết có thể dùng Người tham gia khác nếu đã nhập.
- Lấy số từ tuần gắn với buổi học. Một đoạn không có hậu tố; nhiều đoạn dùng số phần
  đã lưu tương ứng, gồm cả `(1)` cho đoạn đầu.
- Preview được tạo khi xếp hàng; trước khi tải và trước khi mở phiên upload sẽ tính lại
  để nhận thông tin mới hoặc đoạn bổ sung vừa thêm. Cần lưu đủ các phần trước khi upload
  nếu muốn video đầu tiên mang hậu tố `(1)`.
- Thiếu danh xưng, tuần hoặc tên học sinh sẽ báo lỗi trước khi mở phiên upload;
  bổ sung thông tin trong Odoo rồi Thử lại. Không tự đoán giới tính hoặc số tuần.
- Kiểm tra giới hạn YouTube 100 ký tự và loại ký tự `<`, `>`; không tự cắt mất tên/tuần/phần.
- Phiên resumable đã bắt đầu giữ tiêu đề đã gửi; video đã đăng không tự đổi tên.

Nguồn giới hạn API: https://developers.google.com/youtube/data/reference/rest/v3/videos#snippet.title

## Dọn file tạm — 27/10/2026

Từ `edu_video` **17.0.1.4.0**, cron **GVNN: dọn video tạm quá hạn 7 ngày** chạy mỗi
15 phút, độc lập với bật/tắt xử lý upload. Sau khi upload thành công vẫn xóa file ngay như trước.

- Tính hạn từ lần bắt đầu tải (`cache_started_at`), không gia hạn theo mỗi lần ghi thêm dữ liệu.
  File của job cũ chưa có mốc này dùng ngày tạo job; file mồ côi dùng thời gian sửa cuối.
- Chỉ dọn các file `<job_id>.video` trong thư mục cache `data_dir/edu_video/<hash-database>`
  của database đang chạy. Không dọn filestore, attachment, thư mục DB khác hoặc theo symlink.
- Hết hạn 7 ngày sẽ được dọn ở lượt cron tiếp theo. Nếu file đang được worker khóa,
  bỏ qua và thử ở lượt sau; worker cũng chặn tiếp tục xử lý cache đã quá hạn.
- Job chưa upload chuyển **Đã hủy**; job đã có phiên upload chuyển **Cần kiểm tra YouTube**
  để không tự đăng trùng. Job hoàn tất giữ trạng thái/link YouTube và lịch sử.
- Có thể thử lại từ đầu sau khi file đã dọn. Với phiên upload có kết quả chưa rõ,
  kiểm tra kênh rồi dùng **Tạo phiên mới sau kiểm tra**.
- Nếu ổ đĩa từ chối xóa, cron ghi cảnh báo và thử lại; không tự gia hạn cache hoặc tiếp tục upload.
  Video gốc trên Drive và video đã đăng YouTube không bị xóa.

Để áp dụng trên server, cần nâng cấp module `edu_video` và khởi động lại Odoo.
Kiểm tra Scheduled Action mới đang Active và cron worker của Odoo được bật.
Phần trạng thái ngày 24/10 bên dưới là ghi chú lịch sử, không mô tả kết nối production hiện tại.

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

Upload mặc định **Công khai**, không thông báo người đăng ký. Tiêu đề theo mẫu KIMENGLISH bên trên; mô tả có giờ, ngày và thứ. Khi Google trả ID video, hệ thống điền `youtube_url`. YouTube có thể cần thêm thời gian xử lý sau upload.

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
8. Xác nhận đúng kênh đích, kết nối Drive. Bật xử lý nền, thử một video trước, kiểm tra đúng kênh, Công khai, không dành cho trẻ em và bình luận; sau đó bật tự xếp hàng nếu muốn.

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
