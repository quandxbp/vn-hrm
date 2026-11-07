# Bàn giao project Kim Academy

Cập nhật **07/11/2026**, giờ Việt Nam (UTC+7). Đây là đầu mối hiện trạng thay cho
việc đọc tuần tự toàn bộ lịch sử chat. Các trạng thái hàng đợi bên dưới là snapshot,
phải đọc lại DB trước khi xử lý tiếp. Không ghi credential hoặc URL chứa token vào đây.

## Production hiện tại — đã chuyển sang .128 ngày 07/11/2026

- Server **10.77.160.128**, SSH Administrator; source `C:\KimAcademy\source`.
- Domain giữ nguyên https://kimacademy.uk; connector Cloudflare chạy trên .128.
- Compose **`C:\KimAcademy\compose.production.yml`**, project **`kimacademy128`**.
- Code ứng dụng giữ commit `b30fe06b48df6a417903b4f739cd1ddcf7fda3fd`;
  `edu_gvnn=17.0.1.17.4`, `edu_session_review=17.0.2.3.2`. Không nâng phiên bản lúc migrate.
- Đối chiếu cuối: 105 buổi, 74 học viên, 6 giáo viên, 157 lượt tham dự, 55 video jobs,
  59 báo cáo AI, 16 log Zalo; 25 file attachment vật lý, không thiếu file.
- AI `sync`, review/video worker bật; khôi phục 23 cron. Zalo connected và kiểm tra
  trực tiếp nhóm nhận thành công. Không tạo lượt AI hay gửi tin thử khi migrate.
- Giữ nguyên 5 video jobs failed và 18 báo cáo AI failed từ hệ thống cũ; migration
  không cấp quyền gửi lại các yêu cầu mất phản hồi hoặc xóa lịch sử lỗi.
- `.105`: ba container GVNN đã stop, restart policy `no`; dịch vụ Cloudflared dành
  Kim Academy đã stop/Disabled. Volume và backup còn nguyên. Cầu nối Công dân số
  trên .105 và ứng dụng Công dân số trên .128 được kiểm tra vẫn hoạt động.
- Runbook hiện hành: [KIMACADEMY_SERVER_128.md](KIMACADEMY_SERVER_128.md).
  Các địa chỉ `.105` trong snapshot bên dưới là **lịch sử/rollback**, không phải production.

## Quyết định mới nhất 03/11/2026 10:17 UTC+7 — Free Tier, tuần tự

Người dùng đã đổi lựa chọn: **không dùng Batch/Paid Tier**, phân tích trực tiếp tuần tự.
Production đã đặt `review_execution=sync`, `review_enabled=True`; worker video/YouTube
`processing_enabled=True`. Giữ model `gemini-3.5-flash-lite` và key hiện có, không bật Billing.
Chỉ chuyển báo cáo **39 và 47** chưa được Gemini tiếp nhận sang sync; giữ nguyên file và
offset upload. Không tạo thêm bản thay thế cho 32, không tự chạy lại 38 mất phản hồi.
Receipt: `edu_session_review.free_tier_sequential_20261103`. Worker dùng global lock
87425 để chỉ xử lý một báo cáo tại một thời điểm. Cấu hình DB hiện tại ưu tiên hơn default
Batch trong code; không đổi lại Batch khi deploy. Hết quota Free Tier vẫn có thể gặp HTTP429;
timeout inference không được tự gửi lặp khi chưa xác nhận kết quả.

## Lịch sử tiếp nối 03/11/2026 — Batch trước khi đổi lựa chọn

Người dùng đã trả lời: **ưu tiên ổn định, xử lý nền, chấp nhận chờ** và cho phép tạo
**đúng một lượt thay thế báo cáo 32**. Bản `edu_session_review` **17.0.2.3.1** bổ sung
Batch API; xem [SESSION_AI_REVIEW.md](SESSION_AI_REVIEW.md). Các mục 2/5 bên dưới
ghi mốc kiểm chứng; mục 5 có snapshot lịch sử để truy nguyên.

**Đã deploy bản vá:** commit `cc4f97bd2a5c0cfc3fadc7fb858b50ffc327a328`,
upgrade 2.3.1 và login HTTP 200 lúc 09:42 UTC+7. Chế độ `review_execution=batch`.
Local luôn neutralized và mọi cờ gửi thật tắt. Backup nền trước Batch:
`C:\ProgramData\KimAcademyDeploy\backups\ai-batch-20261103-085608`.
Các override tài liệu cũ đã được giữ trong backup và Git stash; source server sạch.

**Điều kiện vận hành phát hiện lúc 09:20 UTC+7:** Google trả `400 FAILED_PRECONDITION`
trước khi tạo job cho báo cáo 47. Schema request, File API và model capability đã đối
chiếu hợp lệ; bảng giá Google ghi Batch không khả dụng ở Free Tier. Không có Batch ID,
không có lượt phân tích được chấp nhận. Bản 2.3.1 giữ nguồn khi bị từ chối, lưu status
an toàn và cho phép **Gửi lại tác vụ nền** trên chính báo cáo. Production giữ
`review_enabled=False` cho tới khi người có quyền thanh toán bật Billing/Paid Tier
trên đúng project API key. Worker video/YouTube độc lập: người dùng đã yêu cầu bật lại,
đã xác nhận `processing_enabled=True` lúc 10:13 UTC+7 ngày 03/11.
Sau deploy đã cập nhật báo cáo 47 thành `batch_status=FAILED_PRECONDITION`, xác nhận
`can_retry_same_review=True`, file 62.602.279 byte vẫn `ready`; thao tác không gọi Gemini.

- Đợt recovery cũ đã có **23/27 done** trước đợt Batch; bản thay thế **46 đã done**.
- Báo cáo **32** mất kết quả được phép tạo một bản mới. Receipt
  `edu_session_review.batch_recovery_20261103` lưu `replacement_id`; luôn đọc receipt
  trước khi tạo lại. Các lần GET/lấy lại tác vụ Batch cũ không tạo lượt phân tích mới.
  Đã tạo bản ghi **47** lúc 08:57 UTC+7, chạy script lần hai vẫn trả receipt này, không tạo thêm.
  Google chưa tạo job do điều kiện Paid Tier; file 62.602.279 byte ở trạng thái `ready`
  còn được giữ để gửi lại cùng báo cáo sau khi Billing hoạt động.
- Báo cáo **38** timeout vẫn chưa có quyền tạo lượt mới; giữ nguyên lịch sử.
- Báo cáo **39** dừng sau các HTTP 503 rõ ràng, chưa có inference được xác nhận,
  `analysis_started=False`, không có JSON: có thể tiếp tục yêu cầu ban đầu bằng Batch
  sau khi đối chiếu nguồn; đã xếp lại **cùng báo cáo 39** bằng Batch, không tạo bản trùng.
- Báo cáo **40** có JSON giữ lại nhưng cờ vào lớp mâu thuẫn. Bản mới hạ nhận định
  thời điểm vào lớp thành cần xác nhận, giữ báo cáo giáo viên; khôi phục offline từ
  phản hồi cũ, không gọi Gemini thêm và không đổi JSON gốc. Đã xác nhận **40 done**,
  hash JSON trước/sau giống nhau.
- Batch lưu UUID trước POST, dò lại khi mất phản hồi, poll sau khoảng một phút và
  cho phép chờ tới 36 giờ từ lúc gửi. Lỗi retrieval không tự tạo job mới. Hủy tác vụ
  phải được xác nhận trước khi xóa nguồn. Không đổi model sang Interactions.
- **78 kiểm thử đạt, 0 lỗi** trên clone local, có kiểm thử mất phản hồi tạo, polling,
  chống trùng, hủy bất đồng bộ, giữ nguồn và mâu thuẫn thời điểm vào lớp.
- Sau deploy, chạy script audit để lấy phiên bản/config, trạng thái Batch, receipt và
  kết quả khôi phục thực tế. Không lấy số terminal của phiên cũ làm điều kiện tiếp tục.

## 1. Mục tiêu và kiến trúc

Repo tên `vn-hrm` nhưng ứng dụng đang vận hành là **Kim Academy / GVNN**, trên
Odoo 17 Community và PostgreSQL 15. Không phục hồi các addon HRM cũ chỉ vì tên repo.

```text
Website / Odoo backend
  edu_landing + vnpt_base + MuK theme
  edu_gvnn: teacher / student / class / week / session / attendee
    ├─ học phí, thu/chi, cảnh báo, lương → vnpt_hrm_dashboard
    ├─ edu_zalo → Node zalo-bridge → nhóm Zalo đã xác nhận
    └─ link Drive (nhiều phần)
        ├─ edu_video → YouTube + ảnh bìa + playlist
        └─ edu_session_review → Gemini → báo cáo nội bộ / modal giáo viên
```

AI và YouTube có hàng đợi riêng. Lỗi nhận xét không được làm mất link YouTube hoặc
chặn upload. AI không tự sửa điểm danh, học phí hay lương.

## 2. Môi trường và phiên bản đã kiểm chứng

| Mục | Hiện trạng |
| --- | --- |
| Nhánh / remote | `feature/edu-gvnn`; `https://github.com/quandxbp/vn-hrm.git` |
| Code ứng dụng đã deploy | `cc4f97bd2a5c0cfc3fadc7fb858b50ffc327a328` (Batch 2.3.1) |
| Production | https://kimacademy.uk; SSH `administrator@192.168.110.105` |
| Repo server / DB | `C:\inetpub\wwwroot\vn-hrm`; **`kimacademy`** |
| Repo local / DB | `D:\Software\vn-hrm`; `kimacademy`, neutralized |
| Containers | web, db đang chạy; zalo-bridge đang chạy và Docker health healthy |
| Google | Drive / YouTube có trạng thái connected trong DB; không đồng nghĩa mọi API luôn sẵn sàng |
| Tự động production | xử lý video/YouTube đã bật lại; nhận xét AI tạm dừng chờ Paid Tier |
| Local | `database.is_neutralized=true`; review/auto-review/video processing đều tắt khi kiểm tra |

| Addon | Phiên bản production |
| --- | --- |
| `edu_gvnn` | `17.0.1.17.2` |
| `edu_video` | `17.0.1.9.0` |
| `edu_session_review` | `17.0.2.3.1` |
| `edu_landing` | `17.0.1.10.0` |
| `edu_zalo` | `17.0.1.4.0` |
| `vnpt_hrm_dashboard` | `17.0.1.1.0` |
| `vnpt_base` | `17.0.1.0` |

Đợt Batch đã đồng bộ source local/server. Ba override tài liệu cũ đã được bảo toàn
trong backup/stash rồi thay bằng nội dung đã gom vào Git, không bị reset mất.
Commit chỉ cập nhật tài liệu sau đó không yêu cầu upgrade lại addon; vẫn phải kiểm tra
Git server để biết đã pull tài liệu mới chưa. Push Git không tự đồng nghĩa deploy.

## 3. Luồng nghiệp vụ và các quyết định phải giữ

- `edu.teacher`, `edu.student` là hồ sơ vận hành, có avatar. Hồ sơ website
  `edu.landing.teacher/student` là nội dung biên tập riêng, không trộn với dữ liệu lương/học phí.
- `edu.session` gắn tuần, ngày/giờ, giáo viên, học viên qua `edu.session.attendee`.
  Điểm danh ảnh hưởng học phí và lương; giữ quy tắc khóa sau chốt lương.
- List **Video buổi học** cho sửa trạng thái đã dạy/nghỉ và danh sách/điểm danh học viên
  theo quyền, có nút **Chi tiết** mở form. Buổi đã chốt lương hoặc testing vẫn bị khóa
  ở các trường tương ứng theo nghiệp vụ; không bỏ khóa chỉ để làm list editable.
- Phần video 1 dùng `google_drive_url` / `youtube_url` trên session. Các phần sau dùng
  `edu.session.recording.part`. Hiển thị và xử lý tất cả phần; không ghi đè phần 1 bằng phần 2.
- `/weekly-schedule` có lịch giáo viên, link YouTube và Session Review. Link cập nhật
  riêng của giáo viên chứa **token bí mật**; không đưa URL thật vào Git, ảnh/log.
  Public chỉ xem lịch/YouTube; nhận xét AI cần token đúng giáo viên hoặc quyền backend.
- Giao diện notebook backend đã đồng bộ phong cách của form session. Login mới nằm
  trong `edu_landing`, đã deploy và nâng cấp; sửa file XML rồi restart đơn thuần có thể
  chưa cập nhật view/asset trong DB.

### Nhập lịch tuần

- Tuần **103** (26/10–01/11/2026): đã nhập 52 buổi, 79 lượt tham dự.
- Tuần **104** (02–08/11/2026): đã nhập production 53 buổi, 79 lượt tham dự;
  nguồn `import_data/Điểm Danh_GVNN (1).xlsx`, sheet `Weekly`, dòng 55–107.
- Người dùng đã xác nhận **MOSHOOD chính là SMITH**: khớp giáo viên Smith hiện có,
  không tạo giáo viên MOSHOOD mới. Không import lại cả file vì thấy tên khác.
- Tuần 104 đã dry-run/rollback, backup trước ghi, đối chiếu lịch và danh sách sau nhập.
  Không ghi đè dữ liệu mà người dùng đã chỉnh sau lần import.

### YouTube

- Production hiện cấu hình **public**, ảnh bìa và playlist tự động bật.
  Các ghi chú cũ nói unlisted là trạng thái lịch sử.
- Ảnh bìa mới: JPEG 3840×2160, dưới 2 MB, có tên giáo viên và học sinh, tuần/ngày/phần.
  Người dùng chọn **chỉ áp dụng video mới**, không backfill ảnh bìa video đã đăng.
- Upload / thumbnail / playlist có trạng thái và cơ chế retry riêng. Không upload lại
  video chỉ vì ảnh bìa hay thêm playlist thất bại. Khi không rõ API đã ghi chưa, kiểm tra
  trước khi tạo lại. Snapshot kiểm tra: 45 video job ở trạng thái done.
- Yêu cầu cũ sửa metadata/playlist trực tiếp của video `bO-2Y3EaW5E` từng bị automatic
  approval review từ chối; chưa có quyền thực hiện lại. Không chạy script sửa cũ từ artifacts.

### Zalo

- Nhóm mặc định đã xác nhận: **KIMACADEMY - TRẢI NGHIỆM NÓI ONLINE**.
  Tự động bật lúc **09:00**, theo `Asia/Ho_Chi_Minh`, gửi bù an toàn trong **6 giờ**,
  chỉ cùng ngày. Snapshot DB state connected không thay được probe trực tiếp.
- Bridge chạy Node với `--tls-max-v1.2`: đã khắc phục handshake mặc định timeout trên
  mạng production; vẫn xác minh chứng chỉ. Không bỏ TLS verification.
- Probe `/check` có xác thực và reconnect bằng phiên đã lưu; monitor mỗi 5 phút tạo
  activity cảnh báo. Chỉ dùng API đọc để kiểm tra kết nối, không gửi tin thử nếu chưa được yêu cầu.
- Retry lỗi trước khi gửi dùng lại **request key và nội dung cũ**; backoff 1/2/4/8/15 phút,
  tối đa 12 lần. Sau khi bắt đầu gửi mà không rõ kết quả: uncertain, không tự gửi lặp.
- Giữ DB và volume `zalo-bridge-data` cùng sổ chống trùng. Không `down -v` hoặc xóa
  volume để sửa kết nối. Xem [ZALO_TLS_COMPATIBILITY.md](ZALO_TLS_COMPATIBILITY.md).

## 4. Sự cố AI ngày 02–03/11: đã sửa gì

Code chính: `custom-addons/edu_session_review/models/review.py`,
`report.py`, `session.py`; kiểm thử ở `tests/test_review.py`.
Chi tiết tiêu chí: [SESSION_AI_REVIEW.md](SESSION_AI_REVIEW.md).

1. **Upload HTTP 400 hàng loạt:** bản sửa timeout trước đó đã giảm chunk xuống 4 MiB,
   trong khi Gemini yêu cầu 8 MiB qua `X-Goog-Upload-Chunk-Granularity`. Đây là regression
   của code, không phải lỗi API key. Commit `27b9355` đọc/lưu granularity thực tế, căn chunk
   và offset theo server; phần cuối được nhỏ hơn. Đã kiểm chứng upload 8 MiB trên phiên thật,
   không gọi inference trong probe đó.
2. **Mất phản hồi upload dù server vẫn nhận byte:** commit `4bedad3` lưu `uploaded_bytes`,
   hiển thị tiến độ, đặt lại ngân sách retry khi query xác nhận có thêm byte. Nếu offset đứng
   yên vẫn giữ giới hạn retry; nếu lùi thì dừng. Không tự đoán offset.
3. **Thông báo lỗi chung chung:** lưu stage và loại lỗi an toàn; lỗi chờ retry hiển thị
   khác lỗi đã dừng. Không ghi key/upload URL hoặc exception chứa secret ra log.
4. **Kết quả AI không đủ căn cứ về học sinh:** trường hợp thiếu dẫn chứng vắng sẽ hạ thành
   chưa xác định/cần kiểm tra thay vì khẳng định vắng. Vẫn từ chối danh tính sai, mốc vượt
   video hoặc cảnh báo trễ/tập trung không có căn cứ. Không biến nhận định AI thành điểm danh.
5. **Phản hồi/JSON đã nhận:** giữ `provider_response` và `result_json` để kiểm tra lại
   offline, không cần trả phí phân tích lần nữa. Đã khôi phục báo cáo 18 từ JSON cũ,
   không gọi Gemini thêm; báo cáo 17 giữ nguyên lịch sử.

Model hiện tại: **`gemini-3.5-flash-lite`**. Timeout connect 10 giây, metadata/query 45,
upload chunk 90, inference 180. `config/odoo.conf`: HTTP 120, cron 300 giây,
`max_cron_threads=2`. Không giảm cron timeout xuống thấp hơn inference.

**60 kiểm thử đạt, 0 lỗi** cho bản 2.2.4 trên DB thử riêng, dùng mock/file giả.
Đã deploy source và upgrade addon production; đã kiểm tra login HTTP 200.
Không thể suy từ kết quả này rằng mọi yêu cầu Google sẽ luôn thành công.

## 5. Việc chưa hoàn tất — đọc trước khi tiếp tục

### Snapshot lịch sử trước Batch — không dùng làm trạng thái hiện tại

Snapshot **03/11/2026 khoảng 01:12 UTC+7**:

- Đợt phục hồi gồm **27 báo cáo**: 26 lỗi upload chưa từng gửi inference và 1 lượt
  mới cho báo cáo cũ số 10 đã được người dùng cho phép.
- **16 done, 2 failed, 9 đang chờ/xử lý/phân tích**. Số này sẽ đổi theo cron.
- Theo báo cáo mới nhất của từng session trong toàn DB: 27 done, 2 failed,
  9 chờ/xử lý/phân tích. Không cộng các lỗi lịch sử đã có bản mới thành công vào lỗi hiện tại.
- Receipt chống tạo lặp nằm trong system parameter
  **`edu_session_review.protocol_recovery_20261102`**. Upload IDs:
  `19,20,21,22,23,24,25,26,27,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45`.
- **Báo cáo 10 / session 31:** người dùng cho phép phân tích mới **đúng một lần**.
  Đã tạo bản thay thế **46**, đang queued ở snapshot. Không tạo thêm chỉ vì thấy 10 còn failed.
- **Báo cáo 32 / session 8:** lỗi mới `ReadTimeout` ở inference sau 180 giây,
  `analysis_started=True`, không có kết quả lưu. Đã gửi câu hỏi xin phép chạy lại đúng một
  lần do có thể tính phí; **chưa nhận câu trả lời tại lúc ghi tài liệu**. Không reset cờ
  hoặc chạy lại tự động. Quyền dành cho báo cáo 10 không áp dụng sang báo cáo 32.
- **Báo cáo 38 / session 48:** cũng vừa gặp inference `ReadTimeout`, không có kết quả
  lưu; chưa tạo lượt thay thế và chưa có quyền phân tích lại. Cần xử lý cùng nguyên tắc
  chống tính phí lặp như báo cáo 32. Chưa có câu trả lời cho phép chạy lại báo cáo này.
- Chưa có HTTP 400 upload tái diễn trong đợt phục hồi đã theo dõi. Không ghi là
  “đã khôi phục toàn bộ” khi còn pending hoặc timeout.

Tại snapshot này cron Active và worker flags từng được khôi phục True. Sau đó Batch bị
`FAILED_PRECONDITION`; trạng thái hiện tại là AI tạm tắt, video/YouTube đã bật lại như đầu tài liệu.
**Không phụ thuộc session ID
của terminal chat cũ** để kiểm tra hiện trạng. Không rerun script tạo recovery nếu chưa đọc receipt.

### Lịch sử lựa chọn xử lý timeout tại 01:12 — đã có trả lời ở cập nhật đầu trang

- API `generateContent` hiện dùng là đồng bộ. Mất phản hồi sau POST không cho biết
  Google đã hoàn tất/tính phí chưa, nên code chủ động không gửi lại để tránh trùng.
- Đã thử capability bằng metadata và input rỗng, không gửi video mới:
  model hiện tại có `batchGenerateContent` nhưng endpoint Interactions trả 404 cho model đó.
  Không mặc định hỗ trợ Interactions chỉ vì tài liệu Google có API này.
- Tại snapshot cũ đã hỏi người dùng chọn nhanh hay Batch, có thể chờ khoảng 24 giờ.
  Khi đó chưa có trả lời. Sau đó người dùng đã chọn Batch và bản 2.3.0 đã deploy;
  không đổi model hoặc tăng timeout đồng bộ. Xem trạng thái tiếp nối ở đầu trang.
- Tài liệu Google tham khảo:
  [Batch API](https://ai.google.dev/gemini-api/docs/batch-api),
  [background execution](https://ai.google.dev/gemini-api/docs/background-execution).

### Cách kiểm tra tiếp, không gửi video/tin nhắn

Script được đưa vào Git để phiên sau không phụ thuộc thư mục artifacts:
[`scripts/ops/inspect_ai_reviews.py`](../scripts/ops/inspect_ai_reviews.py).
Chạy trong repo trên **host có Docker của môi trường cần kiểm tra**:

```powershell
Get-Content -Raw -Encoding UTF8 scripts/ops/inspect_ai_reviews.py |
    docker compose exec -T web odoo shell -d kimacademy --no-http --max-cron-threads=0
```

Nếu server chưa pull commit chứa script, SCP riêng script đã đọc/kiểm tra vào thư mục tạm
rồi pipe nội dung vào lệnh trên, không cần restart web. Script chỉ đọc, luôn rollback,
không gọi Google, không tạo/retry báo cáo và không xuất URL/key/tên học sinh.
Output có giờ UTC, trạng thái mới nhất theo session, receipt phục hồi, loại lỗi và tiến độ byte.

Với lỗi mới: kiểm tra `last_error_stage`, `last_error_type`, `analysis_started`,
`provider_response` / `result_json` bằng công cụ nội bộ có quyền. Không in toàn bộ phản hồi
có thông tin học sinh vào log. Có JSON thì ưu tiên kiểm tra offline; mất kết quả sau inference
thì cần xử lý như yêu cầu chưa xác nhận, không tự tạo lượt trả phí mới.

## 6. Vận hành, triển khai và rollback

Đọc [SERVER_CONNECTION_HANDOFF.md](SERVER_CONNECTION_HANDOFF.md) để SSH/fingerprint.
Mạng nội bộ/VPN và key của máy hiện tại là điều kiện kết nối; không xin private key qua chat.

Trước deploy model/view:

1. Kiểm tra Git cả local/server, commit đích, đúng DB và diff; bảo toàn override. Fetch/merge
   bình thường, không force-push/reset để che thay đổi.
2. Backup DB, filestore và volume Zalo nếu phạm vi có liên quan. Backup thực tế có thể chỉ
   là DB cho một lần sửa schema cụ thể; không coi mọi thư mục backup là full disaster recovery.
3. Lưu cờ ban đầu, tạm tắt `review_enabled` và `processing_enabled`, chờ worker tới checkpoint.
   Không kill một inference đang chạy: có thể mất kết quả trả phí. Kiểm tra không còn advisory
   lock được grant ở namespace **87425 (AI), 87421/87422 (video/channel)** trước stop web.
4. Sau khi an toàn mới stop web, cập nhật source, upgrade đúng module đã cài, start web.
   Kiểm tra log/view/schema, login HTTP 200 và khôi phục **đúng cờ ban đầu**.
5. Kiểm tra trạng thái hàng đợi sau restart. Nếu sửa view bằng ORM ở một process riêng,
   cần signal registry/cache cho process web. Không coi source XML mới là view đã áp dụng.

`deploy/windows/Deploy.ps1` và workflow là khung triển khai, cần đọc/điều chỉnh cho môi trường:
chưa bao gồm mọi yêu cầu pause/checkpoint và backup volume Zalo kể trên. Không tự bật runner
hoặc `KIM_DEPLOY_ENABLED` chỉ vì muốn push code. Lần bàn giao này không thay ứng dụng production.

Rollback phải xét cả source và migration DB; commit cũ không tự hạ schema. Chỉ restore backup
đã xác minh, giữ dữ liệu người dùng phát sinh sau backup. Không dùng `docker compose down -v`.

### Các backup gần nhất đã tạo

Đường dẫn dưới `C:\ProgramData\KimAcademyDeploy\backups`:

| Thư mục | Mục đích |
| --- | --- |
| `week104-import-20261102-200421` | DB trước import tuần 104 và báo cáo đối chiếu |
| `ai-upload-protocol-20261102-234137` | DB trước sửa protocol upload 2.2.3; metadata/source overrides |
| `ai-upload-progress-20261103-000103` | DB trước upgrade 2.2.4; metadata/source overrides |
| `ai-batch-20261103-085608` | DB trước upgrade Batch 2.3.0, metadata/source overrides và stash reference |
| `ai-paid-tier-20261103-094207` | DB đã kiểm tra trước deploy 2.3.1; source server sạch, không cần stash |

Không đưa backup, log riêng, OAuth JSON, Excel, `.env.zalo`, token giáo viên hoặc dữ liệu
provider vào Git. `artifacts/` bị ignore và có thể không tồn tại ở máy mới.

## 7. Kiểm thử và lưu ý kỹ thuật

- Kiểm thử addon trên DB thử/clone neutralized, mock mạng; không bật worker gửi thật.
  Xem các test trong `edu_video`, `edu_session_review`, `edu_zalo` và
  [scripts/gvnn_checks/README.md](../scripts/gvnn_checks/README.md).
- Có 64 test edu_video đạt ở đợt thêm tên học sinh vào thumbnail; 60 test AI đạt ở bản
  2.2.4. Đây là kết quả các đợt sửa tương ứng, không phải mọi test được chạy lại lúc sửa docs.
- Odoo lưu JSON list rỗng thành False: so roster bằng `(roster_snapshot or [])`.
  Tên học viên vận hành được chuẩn hóa uppercase. Không sửa dữ liệu thật theo log lỗi font.
- Cảnh báo cũ: DB production có `vnpt_hrm_attendance` installed nhưng thiếu source addon.
  Chưa xử lý trong task này; không uninstall/xóa dữ liệu để làm sạch log.
- Git local có thể cần `git -c safe.directory=D:/Software/vn-hrm ...` vì ownership;
  không cấu hình wildcard `safe.directory=*`.
- Docker ghi warning lên stderr làm PowerShell báo exit 1 dù script Odoo đã in kết quả.
  Kiểm tra log, exception và kết quả thực; tác vụ deploy nên lấy ExitCode từ process Docker.
- Quy tắc SCSS, cấu trúc module và bắt đầu phiên mới: [CLAUDE.md](../CLAUDE.md).

## 8. Thứ tự phiên tiếp theo

1. Đọc tài liệu này, kiểm tra Git và SSH, chạy script audit mới.
2. Xác nhận Billing/Paid Tier của đúng project API key trong Google AI Studio; đây là
   thao tác tài chính của chủ tài khoản, không tự làm thay.
3. Khi Paid Tier đã hiệu lực, gửi lại chính báo cáo 47, khôi phục riêng worker AI và
   theo dõi Batch ID/kết quả. Báo cáo 39 tiếp tục từ offset upload đã lưu, không tạo bản mới.
4. Bản thay thế 46 đã done; không tạo thêm cho báo cáo 10. Báo cáo 32 đã có đúng một
   bản thay thế 47 theo receipt, không tạo lần nữa.
   Báo cáo 38 chưa có quyền tạo lượt mới. Không hỏi lặp quyền đã cấp.
5. Người dùng đã chọn Batch: không tự đổi lại đồng bộ. Batch có thể cần khoảng 24 giờ;
   kiểm tra retrieval/cleanup rồi cập nhật tài liệu bằng trạng thái đã kiểm chứng.
