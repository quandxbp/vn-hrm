# Bàn giao Kim Website — 23/10/2026

## Cập nhật ảnh thật — 25/10/2026

- `edu_landing` **17.0.1.9.0**, đã upgrade DB local `gvnn`. Tuyển chọn **11 ảnh gốc**
  từ album Facebook do người dùng cung cấp: https://www.facebook.com/mskim.kimacademy/photos.
  Bản JPEG lưu trong `static/src/img/kim/`, permalink nguồn trong `SOURCES.json`.
  Tổng khoảng 3,2 MB, cạnh dài ít nhất 1900px; không hotlink CDN Facebook và không dùng AI sửa ảnh.
- Thay ảnh tĩnh trên trang chủ (banner/4 khóa học/form), Giới thiệu, Tuyển dụng,
  Liên hệ và 4 trang chi tiết khóa học. Logo Kim Academy giữ nguyên.
  Ảnh mầm non dùng học liệu Oxford Phonics, tiểu học dùng lớp thực hành bảng viết,
  thiếu niên dùng thực hành tại bảng, IELTS/SAT dùng đọc sách/trao đổi học tập.
  Ảnh thư viện là hoạt động đọc sách được Facebook chia sẻ, không gắn nhãn là cơ sở trung tâm.
- `models/kim_media.py` + `data/kim_photos.xml` cài ảnh một lần, marker
  `edu_landing.kim_photos_20261025`. So SHA256 ảnh gốc và ảnh Odoo resize để chỉ ẩn
  đúng ảnh mẫu cũ, giữ ảnh người dùng đã tự thay. Không xóa bản ghi hoặc file cũ.
  Tạo 2 thẻ đội ngũ, 2 thẻ vinh danh Cambridge và 6 Highlight trong sự kiện
  “Khoảnh khắc Kim Academy”. Không gán một ngày diễn ra cho ảnh từ nhiều bài đăng.
- Chưa đủ thông tin tên/chứng chỉ từng người: thẻ dùng chú thích trung tính, không gán
  IELTS/CELTA/TESOL hoặc điểm mẫu cho người thật. Bỏ nhãn top 3%/100% mẫu ở phần đội ngũ,
  thay tiêu đề 50.000+ ở phần thẻ học viên bằng “Thành tích học viên Kim Academy”.
  Các số liệu marketing/cảm nhận mẫu ở khu vực khác chưa thuộc đợt thay ảnh này.
  Chưa có ảnh chân dung giáo viên nước ngoài phù hợp: ẩn ảnh mẫu cũ, tab giữ thông báo cập nhật.
- `photos.scss`: thẻ đội ngũ và học viên chuyển hai cột, ảnh ngang object-fit contain,
  giữ đủ người/chứng chỉ; mobile một cột. Các chức năng tab/lọc/slideshow được giữ.
- Đã kiểm tra Chrome: ảnh trên trang chủ + 7 trang có ảnh còn lại dùng nguồn mới,
  không còn URL ảnh stock trong DOM; không có ảnh đã load bị hỏng. Hai tab giáo viên,
  bộ lọc Cambridge hoạt động. Kiểm tra 390px không tràn ngang, ảnh giữ trọn khung;
  đã reset viewport. Console không có lỗi. Chạy lại hàm/upgrade không tạo trùng.
  Published hiện tại: 2 đội ngũ / 2 học viên / 6 hoạt động, 0 ảnh stock; 156 buổi học giữ nguyên.
- Lưu ý XML ID IELTS là `course_ielts_sat`. Đã sửa fallback local sang study-together.
- Backup trước thay dữ liệu: `D:\Projects\vn-hrm-backups\landing-real-photos-20261025\gvnn.dump`.
  Ảnh kiểm tra: `artifacts/landing-real-photos.jpg`. Chưa commit/push/deploy public.

## Cập nhật mới nhất — 25/10/2026: navbar và phần mở đầu đồng bộ

- `edu_landing` **17.0.1.8.0**, đã nâng cấp trên DB local **`gvnn`**. Các ghi chú DB
  `odoo`/`gvnn` ở phần lịch sử bên dưới không mô tả trạng thái máy hiện tại.
- Navbar trong `home.scss` mở rộng selector từ `:has(.edu-home)` sang
  `:has(.edu-landing)`: cùng logo, kích thước, nút tư vấn, nền trong suốt và kính trắng
  khi cuộn, cả desktop/mobile. `landing.js` bỏ vòng affix mặc định trên các trang này
  ngoài editor để tránh transform/padding gây nhảy nội dung. Trang ngoài edu_landing giữ mặc định.
- Giới thiệu, Tuyển dụng, Liên hệ, Chi tiết khóa học và Cảm ơn thêm class `ka-opening`.
  `opening.scss` (nạp sau các style từng trang) dùng nền sáng chuyển sắc, chữ navy,
  Be Vietnam Pro, dòng nhấn Lora nghiêng, breadcrumb/eyebrow/nút tư vấn đồng bộ trang chủ.
  Bố cục và nội dung từng trang được giữ; ảnh mở đầu bo góc 24px.
- Mobile giảm riêng gutter ngang `.edu-landing .row` còn 24px (biến Odoo `--gutter-x`,
  không phải `--bs-gutter-x`) để g-5 không tràn container; khoảng dọc giữ nguyên.
- Đã mở 9 URL trên Chrome desktop và 390×844: `/`, `/gioi-thieu`, `/tuyen-dung`,
  `/lien-he`, 4 slug khóa học, `/contactus-thank-you`. Không tràn ngang sau sửa,
  breadcrumb mobile ở y=104, navbar kết thúc y=77. Đã thử menu mobile và link chuyển trang.
  Link tư vấn cuộn đúng form; header fixed, transform none, nền kính bật, main padding 0.
  Đã reset viewport. Console có lỗi từ extension Chrome `eppiocem.../executors/200.js`,
  không thấy lỗi JS của module trong lượt kiểm tra. Không gửi form/tạo lead.
- Backup: `D:\Projects\vn-hrm-backups\landing-opening-20261025\gvnn.dump`.
  Ảnh: `artifacts/landing-contact-unified.jpg`, `artifacts/landing-careers-unified.jpg`.
  Chỉ cập nhật local, chưa commit/push/deploy internet.

Các phần dưới đây giữ lại bàn giao và quyết định thiết kế của ngày 23/10.

## Đọc trước khi làm tiếp

Đây là trạng thái cuối cùng của đợt thay đổi sau commit `c828b80`, trên nhánh `feature/edu-gvnn`. Khi các ghi chú trung gian trong `CLAUDE.md` khác tài liệu này, dùng trạng thái trong tài liệu này.

- Module website: `custom-addons/edu_landing`, phiên bản **17.0.1.7.0**.
- Đã nâng cấp và kiểm tra bản cuối trên DB local **`odoo`**, Odoo tại `http://localhost:8069`.
- DB `odoo` hiện có `edu_landing`, `edu_gvnn`, `vnpt_hrm_dashboard` ở trạng thái installed.
- DB `gvnn` trên máy này khác bản bàn giao GVNN trước: `edu_landing` installed, `edu_gvnn` uninstalled, dashboard `to install`; đã gặp cảnh báo thiếu các module HRM cũ. Không coi DB này là bản website đã kiểm tra cuối cùng.
- Chưa triển khai các thay đổi trong đợt này lên website public. Git chỉ chứa mã nguồn và ảnh mẫu; dữ liệu nội dung đang sửa trong Odoo không được đẩy cùng Git.

## 1. Menu cấu hình chung

Đã tạo **Kim Website** thành menu/app riêng ở thanh bên, chứa:

| Menu | Model / action XML ID | Nội dung |
|---|---|---|
| Khóa học | `edu.landing.course` / `edu_landing.course_action` | Chức năng cũ, chuyển vị trí menu |
| Hoạt động lớp học | `edu.landing.activity.event` / `edu_landing.activity_action` | Sự kiện, album và chọn ảnh Highlight |
| Học viên tiêu biểu | `edu.landing.student` / `edu_landing.student_showcase_action` | Hồ sơ/thành tích học viên trên website |
| Giáo viên | `edu.landing.teacher` / `edu_landing.teacher_showcase_action` | Hồ sơ giáo viên trên website |

Root menu là `edu_landing.menu_kim_website` trong `views/backend_menus.xml`. Manifest phải nạp file này trước view của các menu con. **Các cấu hình nội dung Kim Academy bổ sung sau này đặt dưới root này.**

Quyền quản lý vẫn là `website.group_website_designer`. App Website chuẩn vẫn dùng cho trình dựng trang và thiết lập Odoo; đăng ký tư vấn vẫn ở CRM.

## 2. Navbar và hero trang chủ

Tham khảo trải nghiệm tại `https://exefpt.vercel.app/`, giữ nội dung và màu thương hiệu Kim Academy:

- Navbar trong suốt trên hero, chuyển sang nền kính trắng khi cuộn. Menu desktop/mobile và dropdown vẫn dùng cơ chế Odoo.
- Hero căn giữa, tiêu đề hai dòng “Khai phóng / tiềm năng”, ảnh nền cũ làm mờ, địa cầu SVG và các biểu tượng học tập nổi nhẹ.
- Giữ hai CTA và bộ chọn khóa học theo tuổi. Bổ sung `aria-pressed` cho chọn tuổi.
- Parallax nhẹ chỉ áp dụng với con trỏ chính xác; dừng animation hero khi ra ngoài viewport, tôn trọng reduced motion.
- “tiềm năng” dùng **Lora Medium Italic** lưu tại `static/src/fonts/`, kèm `Lora-OFL.txt`. Dùng nét nghiêng thật để tránh dấu tiếng Việt bị lệch với Georgia/fallback.
- Nút “Nhận tư vấn” trên navbar dùng đúng `<i class="fa fa-arrow-right" aria-hidden="true"></i>`, đã bỏ mũi tên pseudo-element cũ.

### Nguyên nhân giật navbar đã tìm thấy và cách sửa cuối cùng

Odoo `StandardAffixedHeader` đẩy header lên `translate(0, -100%)` trong khoảng từ chiều cao header đến 300px, đồng thời chèn khoảng đệm `main` khoảng 87px. Đây là xung đột với navbar vốn đã fixed ngay từ đầu của trang chủ.

Chặn CSS đơn thuần chỉ che chuyển động; Odoo vẫn ghi inline style, đọc layout đồng bộ và chạy vòng cập nhật padding. Bản cuối trong `landing.js` bỏ qua `_updateHeaderOnScroll` của `StandardAffixedHeader` **riêng trên `.edu-home`, ngoài Website editor**. Các trang khác giữ hành vi mặc định.

`home.scss` giữ main padding 0 cho trang chủ ngoài editor. Widget navbar riêng dùng listener passive + requestAnimationFrame, chỉ đổi class khi qua ngưỡng; nền kính đặt trong `header::before` và chuyển opacity. Không bật/tắt blur trên mỗi lần chuyển trạng thái.

Đã bỏ animation `stroke-dashoffset` liên tục của SVG lớn và backdrop-filter trên các thẻ nổi/finder. Chưa đo FPS bằng profiler; không diễn giải kiểm tra layout thành số đo hiệu năng.

## 3. Hoạt động lớp học: sự kiện → album → Highlight

### Cấu hình

Trong **Kim Website → Hoạt động lớp học**:

1. Tạo sự kiện, ví dụ “Sự kiện 20/10”; nhập ngày và ghi chú nếu cần.
2. Dùng **Tải nhiều ảnh** để chọn nhiều file cùng lúc, hoặc **Thêm một ảnh** trong album.
3. Mỗi ảnh có tên, ảnh, chú thích, alt, thứ tự và checkbox **Highlight**.
4. Ảnh mới tải lên mặc định **không Highlight**, chỉ lưu trong sự kiện. Chọn Highlight để đưa lên slideshow.

Model ảnh vẫn là `edu.landing.activity`. Field kỹ thuật **`is_published` được giữ nguyên**, nhưng nhãn nghiệp vụ đổi thành **Highlight**, để tương thích ảnh đã công bố trước đó. Không đổi ngược thành một cơ chế xuất bản thứ hai.

`event_id` bắt buộc, liên kết `edu.landing.activity.event`; dùng `auto_join=True` để lọc trạng thái sự kiện trong truy vấn SQL mà không mở quyền album public. Website chỉ lấy ảnh Highlight, sự kiện đang hoạt động và ảnh thuộc website hiện tại hoặc dùng chung.

- Archive sự kiện: ảnh vẫn còn trong album, các Highlight của sự kiện đó không xuất hiện trên website.
- Khôi phục sự kiện: các Highlight được hiển thị lại.
- Xoá sự kiện: xoá ảnh con theo `ondelete='cascade'`.
- Wizard `edu.landing.activity.upload` kiểm tra file ảnh, tạo nhiều ảnh theo thứ tự cuối album, không bật Highlight tự động.

### Chuyển dữ liệu và ảnh mẫu

`data/activities.xml` gọi các hàm riêng:

- `_seed_activity_samples()`: seed một lần 4 ảnh Unsplash có sẵn trong source, marker `edu_landing.activity_samples_created`.
- `_organize_activity_events()`: chuyển ảnh cũ chưa có sự kiện vào “Hoạt động lớp học hiện có”, giữ ảnh, chú thích, thứ tự, website và Highlight.

Marker tách khỏi ảnh nên nâng cấp module không ghi đè nội dung đã sửa và không khôi phục ảnh mẫu đã xoá. Ảnh thật người dùng tải lên vẫn nằm trong database/filestore.

### Giao diện cuối cùng của slideshow

Đã thử dạng một ảnh trong khung cố định nhưng người dùng không chọn phương án đó. **Bản cuối là dải ảnh căn giữa**:

- Ảnh chính ở giữa, hé các ảnh bên cạnh, ảnh bên giảm opacity/scale nhẹ.
- Độ rộng thẻ theo tỷ lệ tự nhiên, giữ trọn ảnh; desktop cùng chiều cao, ảnh rất rộng trên mobile thu nhỏ để vừa vùng xem.
- Không có nền khung lớn, tên ảnh, chú thích, counter, nút next/prev hay pause. Alt vẫn giữ cho trình đọc màn hình.
- Chỉ có dots, tự trượt mỗi **5 giây**, hỗ trợ nhấn ảnh bên cạnh, vuốt ngang và phím trái/phải.
- Không dừng chỉ vì hover. Dừng khi ngoài viewport/tab ẩn; thao tác bàn phím và reduced motion được tôn trọng. Chọn dot bằng chuột tiếp tục tự chạy.
- Track `translate3d` có các bản sao trước/sau để nối vòng đầu/cuối. Bản sao DOM bỏ metadata editor, không được tạo thêm bản ghi Odoo; cleanup khi widget destroy.
- ResizeObserver và sự kiện load ảnh cập nhật kích thước/căn giữa, không đo layout mỗi frame; ưu tiên tải ảnh hiện tại và kề bên.
- Dots chọn theo vị trí DOM, không dựa vào `t-att` số 0 vì QWeb có thể bỏ thuộc tính đó.

## 4. Học viên tiêu biểu — `#hoc-vien`

Trong **Kim Website → Học viên tiêu biểu**, cấu hình:

- Ảnh, họ tên, trường, mô tả ảnh và thông tin bổ sung.
- Nhóm IELTS/Cambridge/SAT, tên chứng chỉ/kỳ thi tuỳ chọn, kết quả dạng chữ (8.0, 1520, 15/15…).
- Thứ tự kéo thả, website, ẩn/hiện.

`edu.landing.student` là model biên tập riêng, **không tự xuất bản dữ liệu vận hành từ `edu.student`**. `_get_landing_students()` chỉ lấy bản công bố đúng website. Khi để trống chứng chỉ, badge lấy tên nhóm; không nhập kết quả thì không có badge.

Giữ giao diện thẻ và bộ lọc Tất cả/IELTS/Cambridge/SAT. Có thông báo khi nhóm trống hoặc chưa có hồ sơ nào. Seed một lần 4 thẻ tĩnh cũ thành dữ liệu editable, marker `edu_landing.student_samples_created`.

## 5. Giáo viên — `#giao-vien`

Trong **Kim Website → Giáo viên**, cấu hình:

- Ảnh, họ tên, chức danh/chuyên môn, chứng chỉ/thành tích và alt.
- Nhóm `center` (tại trung tâm) hoặc `international` (nước ngoài).
- Thứ tự kéo thả, website, ẩn/hiện.

`edu.landing.teacher` là model biên tập riêng, không liên kết đơn giá/lương trong `edu.teacher`. `_get_landing_teachers()` chỉ lấy bản công bố đúng website. Template `edu_landing.teacher_showcase_card` dùng chung cho hai nhóm, giữ layout overlay và tab/bàn phím cũ; nhóm trống hiện thông báo cập nhật.

Seed một lần 4 hồ sơ mẫu cũ, marker `edu_landing.teacher_samples_created`. Những chỉnh sửa và xoá trong quản trị được giữ qua upgrade.

## 6. Phân quyền và dữ liệu

- Website designer quản lý các model nội dung mới.
- Public/portal/internal chỉ đọc ảnh/hồ sơ đã công bố. Ảnh chưa công bố không được đọc trực tiếp qua quyền model.
- Album sự kiện chỉ dành cho biên tập viên; public không được đọc album lưu trữ.
- Mọi hàm lựa chọn nội dung website lọc website hiện tại hoặc bản ghi dùng chung; không dùng sudo để vượt quyền đọc nội dung.
- Các mẫu học viên/giáo viên được chuyển từ nội dung minh hoạ cũ; tên và ảnh thật cần cập nhật trong quản trị.
- Hai manifest cũng giữ tên hiển thị mới: `Kim Academy: Website`, `KIM ACADEMY: Quản lý GVNN`; không đổi tên module kỹ thuật.

## 7. Các file chính

| Phần | File dưới `custom-addons/edu_landing/` |
|---|---|
| Trang chủ / icon navbar | `views/homepage.xml`, `views/header.xml` |
| Hero / navbar | `static/src/scss/home.scss`, `static/src/scss/landing.scss`, `static/src/js/landing.js` |
| Dải ảnh | `static/src/scss/activities.scss`, `static/src/js/activity_slideshow.js` |
| Hub quản trị | `views/backend_menus.xml` |
| Sự kiện và upload | `models/activity.py`, `models/activity_upload.py`, `views/activity_views.xml` |
| Học viên | `models/student_showcase.py`, `views/student_showcase_views.xml` |
| Giáo viên | `models/teacher_showcase.py`, `views/teacher_showcase_views.xml` |
| Truy vấn website | `models/website.py` |
| ACL / rules | `security/ir.model.access.csv`, `security/activity_security.xml`, `security/student_security.xml`, `security/teacher_security.xml` |
| Seed | `data/activities.xml`, `data/students.xml`, `data/teachers.xml` |
| Font / nguồn ảnh | `static/src/fonts/Lora-*`, `static/src/fonts/README.txt`, `static/src/img/CREDITS.txt` |

## 8. Triển khai / làm tiếp trên máy khác

Đọc `CLAUDE.md` cho cách khởi động Docker. Với database đã cài module:

```powershell
docker compose up -d
docker compose exec -T web odoo -d <database> -u edu_landing --stop-after-init --no-http
docker compose restart web
```

Trên DB mới chưa có module dùng `-i edu_landing` thay `-u`. Không dùng nhiều database trong cùng một lệnh `-u`; chạy từng DB riêng. Trên Git Bash thêm `MSYS_NO_PATHCONV=1`.

Sau restart chờ HTTP sẵn sàng; chọn DB bằng `/web/login?db=<database>` trước khi mở `/` khi có nhiều DB. Reload đầy đủ trình duyệt để nhận assets/menu mới. Không hard-code các ID action/menu số từ máy này; dùng XML ID trong code.

**Chuyển nội dung thật sang máy/server khác cần backup/restore cả database và filestore.** Git pull/upgrade không mang theo sự kiện, ảnh upload, hồ sơ người dùng đã nhập. Không reset các marker seed để cố đồng bộ nội dung.

## 9. Kiểm tra đã hoàn tất

Chạy lại cả ba bộ kiểm tra trên DB `odoo` trước khi bàn giao ngày 23/10/2026:

| Script | Kết quả |
|---|---|
| `scripts/check_landing_activities.py` | 26/26 |
| `scripts/check_landing_students.py` | 15/15 |
| `scripts/check_landing_teachers.py` | 15/15 |

Các script chạy bằng Odoo shell, tạo dữ liệu thử rồi rollback. Chúng hiện giả định còn tối thiểu 4 bản ghi có ảnh của từng phần; nếu nội dung thật đã bị xoá bớt, chạy trên DB thử có seed hoặc chỉnh fixture kiểm tra, không tạo lại dữ liệu mẫu trong DB thật chỉ để đạt số đếm.

```powershell
docker compose cp scripts/check_landing_teachers.py web:/tmp/check_teachers.py
docker compose exec -T web sh -c 'odoo shell -d odoo --no-http < /tmp/check_teachers.py'
```

Đã kiểm tra UI list/form/menu, upload multiple, chuyển tab học viên/giáo viên, bàn phím, ảnh public, slideshow tự chạy/dots/vòng đầu-cuối. Desktop và mobile 390px không thấy lỗi console hay tràn ngang. Sai số căn giữa dải ảnh dưới 1px trong lần đo. Chưa benchmark FPS hay kiểm thử tải lớn.

## 10. Phạm vi còn tĩnh / chưa làm

- Thẻ chương trình trên homepage vẫn khai báo tĩnh; model Khóa học đang điều khiển trang chi tiết.
- Tiêu đề/số liệu tổng quan, các badge giới thiệu giáo viên, giáo trình, lời cảm nhận… vẫn là nội dung template; chưa có menu dữ liệu cho các phần đó.
- Không thêm trang album sự kiện public, không tự xuất bản tất cả ảnh trong album.
- Không sửa các vấn đề module/DB cũ của `gvnn` trong đợt website này.
- Không có yêu cầu nghiệp vụ website mới nào đang làm dở tại thời điểm bàn giao; tiếp tục theo yêu cầu mới của người dùng.
