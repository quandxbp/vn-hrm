# vn-hrm

> **Bàn giao GVNN/Zalo mới nhất (24/10/2026):** đọc [docs/SESSION_HANDOFF_2026-10-24.md](docs/SESSION_HANDOFF_2026-10-24.md)
> trước khi tiếp tục. DB local hiện dùng **`gvnn`**, đã nhập thử 155 buổi tuần 100–102.
> Có module `edu_zalo` + bridge `zca-js`; gửi thủ công hoạt động, tự động 12:00 vẫn tắt.
> Mẫu cuối gom theo giáo viên, mỗi tiết một dòng và link học cuối đoạn. Ghi chú này cập nhật trạng thái local mới hơn tài liệu website ngày 23/10.

> **Auto deploy Windows (đang chuẩn bị, chưa bật trên server):** xem [docs/WINDOWS_DEPLOY.md](docs/WINDOWS_DEPLOY.md).
> Workflow GitHub Actions chạy khi push `feature/edu-gvnn`, cần runner Windows label `kim-production`, worker/config ngoài repo
> và repository variable `KIM_DEPLOY_ENABLED=true`. Chưa cài runner hoặc chạy deploy thật. Không coi push code là đã deploy server.

Odoo 17 chạy bằng Docker. Hiện dùng cho trung tâm luyện nói tiếng Anh với giáo viên nước ngoài (GVNN): module `edu_gvnn` thay file `TỔNG HỢP_GVNN.xlsx`, kèm `edu_landing` (landing page) dùng chung server. Phần HRM của VNPT là mã cũ, không còn dùng cho GVNN.

> **Bàn giao mới nhất (23/10/2026):** đọc [docs/WEBSITE_HANDOFF.md](docs/WEBSITE_HANDOFF.md) trước khi làm tiếp website: có trạng thái cuối cùng của navbar/hero, dải ảnh sự kiện + Highlight, menu Kim Website, học viên/giáo viên động, triển khai và kiểm tra. `edu_landing` hiện là **17.0.1.7.0**, đã kiểm tra trên DB local **`odoo`**. Source nghiệp vụ GVNN đã xong giai đoạn 1–8, nhưng trạng thái DB `gvnn` của máy này khác bản bàn giao cũ; không mặc định DB đó đã sẵn sàng. Với nghiệp vụ GVNN, đọc [docs/GVNN_PLAN.md](docs/GVNN_PLAN.md) và đối chiếu DB thực tế trước khi sửa.

## Chạy

```sh
docker compose up -d            # web (odoo:17.0) + db (postgres:15)
docker compose logs -f web
```

- Web: http://localhost:8069. Master password và DB credential nằm trong `config/odoo.conf`.
- `docker compose` có `command: -u vnpt_base`, nên mỗi lần web khởi động lại đều nâng cấp `vnpt_base`.
- Server có nhiều database và `dbfilter` đang trống, nên phải chọn DB bằng `/web/login?db=<tên>` trước khi vào `/`.

## Dựng trên máy mới

Dữ liệu (DB `gvnn`) nằm trong volume Docker của máy cũ, **không có trong git**. Máy mới phải tạo lại DB rồi import lại từ Excel.

1. Cài Docker Desktop và mở nó lên. `git clone https://github.com/quandxbp/vn-hrm.git`, rồi `git checkout feature/edu-gvnn`.
2. Copy `TỔNG HỢP_GVNN.xlsx` từ máy cũ vào thư mục gốc repo. File này không nằm trong git vì là dữ liệu thật của trung tâm.
3. `docker compose up -d`, chờ `http://localhost:8069/web/login` trả 200 (30-60 giây).
4. Tạo DB `gvnn` và cài module:
   ```sh
   MSYS_NO_PATHCONV=1 docker compose exec -T web odoo -d gvnn -i edu_gvnn,vnpt_hrm_dashboard,edu_landing,muk_web_theme,muk_web_appsbar,muk_web_chatter,muk_web_colors,muk_web_dialog --without-demo=all --stop-after-init --no-http
   ```
5. `docker compose restart web`, rồi vào `http://localhost:8069/web/login?db=gvnn`. DB tạo bằng dòng lệnh có tài khoản `admin` / `admin` mặc định, hãy đổi mật khẩu ngay.
6. Import dữ liệu: menu Cấu hình > Import Excel, chọn file ở bước 2, từ 01/01/2026. Đối chiếu kết quả với bảng ở mục 5 của `docs/GVNN_PLAN.md`.
7. Trước khi sửa code: đọc `docs/GVNN_PLAN.md`. Các script kiểm tra nằm ở `scripts/gvnn_checks/` (xem README trong đó).

**Chưa kiểm chứng:** lệnh ở bước 4 chưa được chạy lại nguyên văn trên một DB trống. Phần `-i edu_gvnn,vnpt_hrm_dashboard` đã cài sạch trên DB tạm, còn `edu_landing` và các module `muk_web_*` đã cài sạch trên `gvnn` ở giai đoạn 1. Nếu bước 4 báo lỗi, đọc log bằng `grep -E " ERROR | CRITICAL |Traceback|ParseError"`.

**Bảo mật:** `config/odoo.conf` nằm trong git và repo GitHub đang để công khai. Master password và mật khẩu DB đều rất ngắn (4 ký tự), cổng Postgres 5432 cũng được mở ra máy chủ. Đừng chạy cấu hình này trên máy có thể truy cập từ ngoài; nên đổi hai mật khẩu đó và đưa file ra khỏi git.

## Cấu trúc

- `custom-addons/`: code của dự án (mount vào `/mnt/extra-addons`).
  - `edu_gvnn`: nghiệp vụ GVNN (giáo viên và đơn giá, lớp, học viên, buổi học, thu học phí, kỳ lương, cảnh báo tuần, báo cáo tài chính, import/export Excel). Phụ thuộc `base`, `mail`, `web`, `vnpt_base`; không dùng `hr` hay `account`.
  - `vnpt_hrm_dashboard`: dashboard GVNN (client action OWL `owl.vnpt_hrm_dashboard`, model `edu.dashboard`), trang chủ sau khi đăng nhập. Phụ thuộc `edu_gvnn`.
  - `vnpt_base`: nền dùng chung (đăng nhập, tiêu đề, địa chỉ VN). Còn dùng.
  - Các module HRM cũ (`vnpt_hrm`, `vnpt_hrm_attendance`, `vnpt_hrm_payroll`) đã bị xoá ngày 2026-10-09 theo yêu cầu của người dùng. Còn trong lịch sử git (commit `7083bfa` trở về trước) nếu cần khôi phục.
  - `muk_theme/*`: theme backend MuK, đã chỉnh sửa (sidebar, navbar, màu).
  - `edu_landing`: landing page Website, cần `website` + `website_crm` (Community) và `vnpt_base` (giữ file logo `vnpt_base/static/src/img/kim-academy-logo.png`, dùng cho menu của landing).
- `required-addons/`: hiện trống (chỉ còn `.DS_Store`). `hr_payroll` (Enterprise, OEEL-1) đã xoá cùng HRM cũ. Thư mục vẫn được mount vào `/mnt/enterprise` và nằm trong `addons_path`, nên giữ lại.
- DB đang dùng là `gvnn`. Các DB cũ: `test` có cài `vnpt_hrm`, `hr_payroll`, `vnpt_hrm_attendance`; `edu`, `edu2`, `edu3` chỉ có `vnpt_hrm_attendance` (rỗng). Sau khi xoá module, log báo "Some modules are not loaded" khi nạp các DB này. Trang đăng nhập của chúng vẫn mở, chưa kiểm tra xa hơn. Chỉ `gvnn` còn được đảm bảo chạy.
- **Lỗi đã biết khi có nhiều DB:** nếu một DB khác được nạp trước `gvnn` sau khi khởi động server, `/web/login?db=gvnn` trả 403 (`AccessError` đọc `website.menu`). Mở `gvnn` trước thì bình thường. Lỗi vẫn xảy ra khi các module HRM cũ còn nguyên, nên không do việc xoá chúng. Chưa rõ nguyên nhân gốc; nghi do `website` cần `dbfilter` khi có nhiều DB. Cách tránh: đặt `dbfilter = ^gvnn$` trong `config/odoo.conf` (chưa đặt, vì làm vậy các DB khác sẽ không truy cập được qua web).
- `config/odoo.conf`: mount vào `/etc/odoo`.

## Lệnh thường dùng

Chạy trong Git Bash trên Windows: luôn đặt `MSYS_NO_PATHCONV=1`, nếu không Git Bash đổi `/usr/...` thành đường dẫn Windows và lệnh trong container hỏng.

```sh
# Cài / nâng cấp module mà không mở HTTP
MSYS_NO_PATHCONV=1 docker compose exec -T web odoo -d <db> -u <module> --stop-after-init --no-http
docker compose restart web      # để server đang chạy nhận code / assets mới

# Kiểm tra lỗi sau khi cài
... 2>&1 | grep -E " ERROR | CRITICAL |Traceback|ParseError"

# Odoo shell (đọc script từ stdin)
MSYS_NO_PATHCONV=1 docker compose exec -T web sh -c "odoo shell -d <db> --no-http" < script.py
```

Sau khi restart, Odoo cần khoảng 30-60 giây mới phục vụ trang. Chờ `/web/login` trả 200 rồi mới kiểm tra.

Python trên máy là Python Windows: nó không đọc được đường dẫn `/tmp/...` của Git Bash, phải dùng `cygpath -m`.

## Quy ước và lưu ý

- **Phụ thuộc module:** view nào kế thừa view của module khác thì module đó phải có trong `depends`. Ví dụ: `vnpt_hrm` cần `survey` vì `survey_invite_views.xml`.
- **Biến SCSS của theme:** màu, bo góc và viền lấy từ biến của Odoo (`$o-brand-primary`, `$o-gray-*`, `$o-view-background-color`), không hard-code. Nhờ vậy dashboard, sidebar và navbar cùng đổi theo màu chủ đạo.
  - `muk_theme/muk_web_theme/static/src/scss/colors.scss`: màu sidebar.
  - `muk_theme/muk_web_appsbar/static/src/scss/variables.scss`: độ rộng sidebar (`$mk-sidebar-large-width`, hiện là 208px).
  - Navbar đổi màu qua các biến CSS `--NavBar-*` trong `muk_web_theme/.../navbar/navbar.scss`.
- **Bẫy của bộ biên dịch SCSS Odoo:**
  - `min()` / `max()` trộn đơn vị (vd. `vh` với `px`) làm Sass báo lỗi. Odoo khi đó âm thầm dùng bundle cũ, nên trang mất style mà không báo lỗi gì rõ ràng. Bọc bằng `unquote("min(88vh, 820px)")`. `clamp()` thì không bị.
  - Không đặt `@import url(...)` Google Fonts trong SCSS: Odoo cắt URL tại dấu `;` (`wght@400;500`) và làm hỏng cả bundle. Nạp font bằng `<link>` trong template (xem `edu_landing/views/assets.xml`).
  - Kiểm tra bundle: tải CSS của `web.assets_frontend` / `web.assets_backend` và tìm chuỗi `css_error_message`.
- **Chart.js:** dùng bản có sẵn trong Odoo qua `loadBundle("web.chartjs_lib")`, không tải từ CDN.
- **Màu chữ:** đạt tương phản WCAG AA (4.5:1). Màu nút cam và chữ trên nền xanh đã được chỉnh theo yêu cầu này.

## edu_landing

**Trạng thái cuối cùng và cách làm tiếp:** [docs/WEBSITE_HANDOFF.md](docs/WEBSITE_HANDOFF.md). Các ghi chú ngày 23/10 bên dưới là nhật ký quá trình; menu hiện tại là **Kim Website** và slideshow hiện tại là **dải ảnh căn giữa chỉ có dots**, thay cho các bản trung gian có khung cố định/nút điều khiển.

- Cấu hình section `#giao-vien` (2026-10-23): menu **Kim Website → Giáo viên**, model biên tập riêng `edu.landing.teacher` (không liên kết đơn giá/lương trong `edu.teacher`). Tải ảnh, tên, chức danh/chuyên môn, chứng chỉ/thành tích, nhóm `center`/`international`, thứ tự, website và ẩn/hiện. `_get_landing_teachers()` chỉ lấy bản công bố đúng website; `teacher_showcase_card` dùng chung hai nhóm, giữ style/tab/bàn phím và hiển thị thông báo khi nhóm rỗng. Seed một lần 4 hồ sơ mẫu cũ bằng marker `edu_landing.teacher_samples_created`, không ghi đè chỉnh sửa hay khôi phục bản đã xoá. Designer quản lý, public/portal/internal chỉ đọc bản công bố và ảnh tương ứng. Đã upgrade `17.0.1.7.0` trên DB `odoo`; tests `scripts/check_landing_teachers.py` đạt 15/15 (rollback), kiểm tra list/form trong Kim Website, hai tab mỗi tab 2 hồ sơ, điều khiển bàn phím và mobile 390px không tràn ngang/lỗi JS.

- Hub cấu hình **Kim Website** (2026-10-23): root menu/app `edu_landing.menu_kim_website` trong `views/backend_menus.xml`, nạp trước các view con. Đã chuyển ba menu hiện có Khóa học, Hoạt động lớp học, Học viên tiêu biểu từ Website → Site sang hub này, giữ XML ID/action/quyền Website designer và dữ liệu. **Mọi màn hình cấu hình nội dung Kim Academy bổ sung sau này đặt dưới `menu_kim_website`.** Website chuẩn vẫn dùng cho trình dựng trang và thiết lập Odoo; CRM đăng ký vẫn ở CRM. Đã nâng cấp `17.0.1.6.1` trên DB `odoo` và xác nhận root cùng ba mục con trên UI.

- Cấu hình section `#hoc-vien` (2026-10-23): menu Website → Site → **Học viên tiêu biểu**, model biên tập riêng `edu.landing.student` (không nối dữ liệu vận hành `edu.student`). Tải ảnh, tên, trường, nhóm IELTS/Cambridge/SAT, nhãn kỳ thi tuỳ chọn, kết quả dạng chữ, thông tin bổ sung, website, ẩn/hiện và thứ tự kéo thả. `_get_landing_students()` lọc bản ghi công bố theo website; trang chủ render động, giữ giao diện và tab lọc cũ, thêm trạng thái rỗng cho toàn section/nhóm không có kết quả. Chưa nhập kết quả thì không có badge, nhãn kỳ thi để trống lấy tên nhóm. Seed một lần 4 thẻ mẫu cũ thành dữ liệu editable; marker `edu_landing.student_samples_created` giữ chỉnh sửa/xoá qua upgrade. Designer quản lý, public/portal/internal chỉ đọc bản công bố (bao gồm ảnh). Đã upgrade `17.0.1.6.0` trên DB `odoo`; `scripts/check_landing_students.py` đạt 15/15 và rollback; kiểm tra list/form quản trị, tab IELTS=2/Cambridge=1/SAT=1/Tất cả=4 và mobile 390px không lỗi JS/tràn ngang.

- Dải ảnh căn giữa (2026-10-23): slideshow đổi sang flex track với thẻ rộng theo tỷ lệ tự nhiên, ảnh chính ở giữa, ảnh hai bên giảm opacity/scale nhẹ; không còn khung nền bao quanh. Desktop ảnh cùng chiều cao, ảnh rất rộng trên mobile thu nhỏ để giữ trọn ảnh. Track translate3d tự trượt 5 giây, bản sao DOM trước/sau tạo vòng lặp; dots, nhấn ảnh bên cạnh, bàn phím và vuốt vẫn hoạt động. ResizeObserver và ảnh load cập nhật căn giữa, chỉ preload ảnh hiện tại/kề bên; không đo layout mỗi frame. Clone bỏ metadata Website editor, được xoá và khôi phục track khi widget destroy. Đã kiểm tra 6 ảnh thực tế, vòng đầu↔cuối (sai số tâm <1px), mobile 390px giữ tỷ lệ, không tràn ngang/lỗi JS. Quản lý sự kiện/Highlight giữ nguyên.

- Hiển thị slideshow nhiều tỷ lệ (2026-10-23): ảnh dùng `object-fit: contain` trong khung cao ổn định, nền xanh nhạt, không crop ảnh ngang/dọc/vuông. Website bỏ tên/chú thích ảnh, counter, nút trước/sau và pause; chỉ còn dots và tự chuyển 5 giây. Hover không dừng; chọn dot bằng chuột tiếp tục tự chạy, focus bàn phím/reduced motion vẫn được tôn trọng. Chọn dot dựa vào vị trí DOM (không dùng số 0 trong t-att vì QWeb bỏ thuộc tính giá trị 0). Giữ metadata trong quản trị và alt trên website. Đã kiểm tra với 6 ảnh thực tế có tỷ lệ khác nhau, tự chuyển/dots, khung desktop 620px và mobile 480px không nhảy, không tràn ngang/lỗi JS.

- Album theo sự kiện + Highlight (2026-10-23): menu `activity_action` nay mở `edu.landing.activity.event` (tên, ngày, ghi chú, album, tổng ảnh/highlight). `edu.landing.activity.event_id` bắt buộc; `_organize_activity_events()` chuyển ảnh cũ vào “Hoạt động lớp học hiện có”, giữ nguyên ảnh/chú thích/thứ tự/website/trạng thái. Field kỹ thuật `is_published` giữ để tương thích dữ liệu, nhãn đổi thành **Highlight**; chỉ ảnh highlight thuộc sự kiện đang hoạt động xuất hiện trên slideshow. Event chỉ Website designer được đọc/quản lý; public chỉ đọc các ảnh highlight, không truy cập album lưu trữ. Many2one `event_id` dùng `auto_join=True` để lọc trạng thái sự kiện trong SQL mà không mở quyền album public. Nút **Tải nhiều ảnh** mở wizard `edu.landing.activity.upload` dùng many2many_binary; ảnh mới mặc định không highlight, kiểm tra file ảnh và thêm theo thứ tự cuối album. Archive sự kiện ẩn mọi highlight; xoá sự kiện xoá ảnh con. Nâng cấp `17.0.1.5.0` trên DB `odoo`, tests `scripts/check_landing_activities.py` đạt 26/26 (rollback), đã kiểm tra UI danh sách sự kiện, album và checkbox, hộp upload có input multiple. `-u edu_landing` rồi restart khi deploy.

- Slideshow Hoạt động lớp học (2026-10-23): model `edu.landing.activity`, menu Website → Site → Hoạt động lớp học (`activity_action`). Website designer thêm/sửa/xoá ảnh, tải ảnh, chú thích/alt, ẩn/hiện và kéo thả thứ tự; public/portal/internal chỉ đọc ảnh công bố. `_get_landing_activities()` lọc theo website và thứ tự. Seed một lần 4 ảnh Unsplash ngang 1600×900 từ `static/src/img/activities/` bằng `_seed_activity_samples()` + marker `edu_landing.activity_samples_created`; không ghi đè chỉnh sửa hay khôi phục ảnh đã xoá khi upgrade. `activity_slideshow.js` tự chuyển 5 giây, trước/sau, dots, pause, bàn phím và vuốt ngang; dừng khi hover/focus, tab ẩn, ngoài viewport hoặc reduced motion. Chuyển ảnh chỉ dùng opacity, khung ảnh cố định. Không ảnh: hiện thông báo cũ; một ảnh: không có nút điều khiển. Đã upgrade DB `odoo`, kiểm tra quản trị list/form, 4 ảnh, nút chuyển/pause/autoplay và mobile 390px; `scripts/check_landing_activities.py` đạt 13/13, rollback toàn bộ dữ liệu thử. Cần `-u edu_landing` và restart web khi triển khai nơi khác.

- Tối ưu cuộn hero (2026-10-23): bản chặn CSS trước chỉ che được chuyển động; `StandardAffixedHeader` vẫn ghi inline styles, đọc layout đồng bộ và chạy vòng cập nhật padding. `landing.js` nay bỏ qua `_updateHeaderOnScroll` của widget đó riêng trên `.edu-home` ngoài editor, giữ cơ chế mặc định ở các trang khác. Navbar riêng chỉ đổi class khi qua ngưỡng. Bỏ animation `stroke-dashoffset` của SVG lớn và backdrop-filter trên thẻ nổi/finder, giữ chuyển động transform và parallax. Kiểm tra runtime: qua 145/1684px không còn inline transform/padding từ Odoo, không có lỗi JS. Chưa đo FPS bằng profiler; blur và SVG là các nguồn chi phí render xác định từ mã, chưa định lượng mức đóng góp.

- Sửa khựng khi chuyển trạng thái navbar (2026-10-23): đo được Odoo thêm `padding-top: 87px` lên `main` tại ngưỡng affixed, làm toàn bộ nội dung nhảy xuống. Trang chủ nay giữ `main` padding 0 (ngoại trừ Website editor); nền kính đặt trong `header::before` và chỉ chuyển opacity, không bật/tắt backdrop-filter. Đã đo ở các mốc cuộn 0/145/316/1684px: tọa độ nội dung trong trang không đổi, header luôn ở top 0.

- Sửa navbar/tiếng Việt hero (2026-10-23): header trang chủ cố định có `transform: none !important` để không bị `StandardAffixedHeader` của Odoo đẩy lên `-100%` trong khoảng cuộn từ chiều cao header đến 300px. Giữ hiệu ứng nền khi cuộn. Chữ nghiêng "tiềm năng" dùng Lora Medium Italic lưu tại `static/src/fonts/` (kèm OFL), thay Georgia/italic tổng hợp để dấu tiếng Việt liền glyph; `font-synthesis: none` và giảm letter spacing âm.

- Navbar và hero trang chủ (2026-10-23): tham khảo trải nghiệm `https://exefpt.vercel.app/`. Giữ nội dung, CTA, bộ lọc tuổi và toàn bộ section phía sau. `homepage.xml` thêm địa cầu SVG trang trí, tiêu đề hai dòng; `home.scss` đặt navbar trong suốt trên hero, nền kính trắng khi cuộn (cả header affixed của Odoo), ảnh nền mờ và bố cục trung tâm. `landing.js` thêm parallax nhẹ theo con trỏ, dừng animation khi hero ngoài màn hình, hỗ trợ reduced motion và `aria-pressed` cho chọn tuổi. Không có thư viện/CDN mới. Đã nâng cấp `edu_landing` trên DB local `odoo`, `gvnn`; kiểm tra website trên DB `odoo`. Lưu ý DB local `gvnn` trên máy này khác bản bàn giao: `edu_gvnn` chưa cài, dashboard `to install`, còn cảnh báo thiếu các module HRM cũ; không xử lý việc đó trong thay đổi giao diện.

- CRM → Đăng ký từ website: `views/website_registration_views.xml`, list/form/search riêng cho `crm.lead` với domain `edu_website_registration=True`, không có bộ lọc My Pipeline mặc định. Các cột mặc định: ngày đăng ký, họ tên, điện thoại, email, chương trình, trạng thái và người phụ trách. `models/crm_lead.py` thêm cờ nguồn và trường chương trình; migration XML function nhận diện dữ liệu cũ bằng tiêu đề + dòng chương trình trong description, không thay CRM type. `controllers/forms.py` kế thừa WebsiteForm CRM để đặt cờ/trường từ marker `edu_registration=1` của form dùng chung; giữ nguyên quyền CRM. Đã upgrade cả hai DB, thử submit mới + archive test và kiểm tra UI list/form trên odoo.

- Form tư vấn: `static/src/js/consultation_form.js` mở rộng widget Odoo chỉ cho form có `data-edu-database`. Trước khi submit gọi JSON endpoint `/edu-landing/form-session` lấy CSRF hiện tại, chặn gửi nếu tab đã chuyển DB; giữ nguyên route tạo CRM và kiểm tra CSRF/reCAPTCHA của Odoo. Xử lý lỗi kết nối bằng thông báo, giữ dữ liệu nhập. Đã thử gửi thật bằng public và admin trên DB odoo, đối chiếu hồ sơ CRM và archive hồ sơ kiểm thử.

- Trang cảm ơn `/contactus-thank-you`: `views/thank_you.xml`, `static/src/scss/thank_you.scss`; kế thừa `website.contactus_thanks_ir_ui_view` (XML ID view, khác XML ID website.page). Giữ URL chuyển hướng form và noindex mặc định. Hiển thị xác nhận tiếng Việt, bước tư vấn tiếp theo, hotline Kim, link chương trình/liên hệ/chỉ đường; loại bỏ nội dung và địa chỉ mẫu Odoo. Đã kiểm tra desktop/mobile, không tạo lead thử.

- Chỉ đường Google Maps dùng template chung `edu_landing.directions_link` trong `views/map.xml`: `/maps/dir/?api=1&destination=11.538931%2C106.8911376`. Dùng tại trang Liên hệ và địa chỉ footer. Khối kéo thả `website.s_map` cũng được kế thừa để đặt tọa độ/iframe mặc định đúng trung tâm, zoom 17. Đã kiểm tra 9 liên kết trên 8 trang local và cấu trúc map kế thừa.

- Trang liên hệ riêng `/lien-he`: `views/contact.xml`, `static/src/scss/contact.scss`. Menu Liên hệ và footer dẫn đến trang này; sync menu nhận lại alias `/#lien-he` và `/contactus`. Trang gồm hotline/email/Facebook, địa chỉ với link tìm kiếm Google Maps và form CRM dùng chung. Template registration hỗ trợ `registration_title`/`registration_description` tùy trang; mặc định giữ nội dung cũ. Đã upgrade trên DB `odoo`, `gvnn` và kiểm tra desktop/mobile, form các trang khác.

- Chi tiết khóa học: route `/khoa-hoc/<slug>`, model `edu.landing.course`, menu Website → Site → Khóa học dành cho website designer. Có ảnh upload, độ tuổi, mục tiêu, giới thiệu HTML và số học viên còn nhận cập nhật thủ công (`seats_confirmed`/`seats_remaining`); chưa xác nhận hiển thị đang cập nhật, xác nhận 0 hiển thị đủ số lượng. Form dùng chung chọn sẵn chương trình bằng `course_program`. Seed 4 khóa học từ nội dung mẫu trong `data/courses.xml` với noupdate để giữ chỉnh sửa khi upgrade. Public/portal/internal chỉ đọc khóa học công bố; website designer quản lý. Homepage còn dùng thẻ chương trình tĩnh, các link dẫn đến slug seed. Cần nâng cấp module khi deploy để tạo model, quyền và dữ liệu.

- Trang tuyển dụng `/tuyen-dung`: `views/careers.xml` và `static/src/scss/careers.scss`; submenu Tuyển dụng trong Về Kim Academy và liên kết footer. Nội dung gồm môi trường, giá trị, nhóm công việc giáo viên/nhân sự và liên hệ email. Chưa có JD được xác nhận, nên hiển thị trạng thái đang cập nhật; dùng email công khai `kimacademy.edu@gmail.com`, chưa có form tải CV hoặc tích hợp HR Recruitment. Đã nâng cấp module trên DB `odoo`, `gvnn`; kiểm tra UI và CSS trên website `odoo`.

- Theo y?u c?u ti?p theo: section `thanh-tich` v? `giao-vien` ?? kh?i ph?c b? c?c, n?n, th? ?nh g?c; gi? typography hi?n t?i. `home.scss` ch? c?n ghi ?? typography cho hai section n?y.

- Đồng bộ hình thức trang chủ với trang giới thiệu (2026-10-13): `edu-home` + `static/src/scss/home.scss`. Tiêu đề phụ, tiêu đề chính, nút và form dùng style chung trong `landing.scss`; trang chủ dùng nền navy/trắng/xanh nhạt, thẻ ảnh kèm phần chữ riêng, bố cục chứng nhận/thống kê hai cột và một cột trên mobile. Giữ nội dung, neo, lọc độ tuổi, lọc thành tích và điền sẵn chương trình. Clearfix `container::before/after` của Odoo phải ẩn khi container dùng CSS grid để không chiếm ô.
- Trang giới thiệu `/gioi-thieu` (2026-10-13): `views/about.xml`, CSS riêng `static/src/scss/about.scss`, bản ghi `website.page` công khai. Submenu Giới thiệu trung tâm, nút Câu chuyện của chúng tôi và footer đều dẫn đến trang này. Nội dung biên soạn cho Kim Academy theo cấu trúc tham khảo YOLA; không dùng ảnh, câu chuyện sáng lập hoặc số liệu của YOLA. Lịch sử/người sáng lập của Kim Academy chờ người dùng bổ sung.
- Form tư vấn đã tách thành `views/registration.xml` (`edu_landing.registration`), dùng chung trang chủ và giới thiệu. Template gọi cần đặt biến `img` trỏ đến thư mục ảnh. Đã nâng cấp trên DB `odoo` và `gvnn`; kiểm tra desktop/mobile, liên kết menu, ảnh và form.
- Navbar (2026-10-12): Về Kim Academy (4 submenu), Chương trình học, Học viên & Hoạt động (3 submenu), Liên hệ, nút Nhận tư vấn. Website một trang; chương trình cụ thể bổ sung sau. Điểm cuộn: `gioi-thieu`, `phuong-phap`, `giao-vien`, `uy-tin`, `chuong-trinh`, `hoc-vien`, `cam-nhan`, `hoat-dong`, `lien-he`, `dang-ky`.
- `views/menus.xml` gọi `website._sync_edu_landing_menus()` khi nâng cấp; `post_init_hook` dùng chung hàm đồng bộ khi cài mới. Khi đổi menu trang riêng sang neo phải xoá `page_id`, nếu không Odoo vẫn dẫn tới trang cũ. Menu mobile tự đóng sau khi chọn neo.
- Đã áp dụng navbar trên DB `gvnn` và `odoo`; tab website của người dùng ngày 2026-10-12 dùng DB `odoo` (xác nhận từ log HTTP). Mục Hoạt động lớp học hiện là thông báo đang cập nhật, chờ nội dung thật.
- Ghi đè `website.homepage` (vùng `#wrap`) và footer. Các khối nằm trong `oe_structure` nên vẫn sửa được bằng trình dựng kéo thả.
- Form đăng ký gửi tới `/website/form/crm.lead` và tạo lead. Các trường tự đặt (chương trình, cơ sở) được ghi vào `description` của lead.
- Menu neo (`/#chuong-trinh`, ...) được tạo trong `hooks.py` (`post_init_hook`) và gắn vào `website.menu_id` của từng website, không gắn vào `website.main_menu`. Cách khai báo bằng XML với `eval="obj()..."` không chạy được trên Odoo 17.
- **Nội dung và ảnh đều là mẫu.** Số liệu, tên, lời cảm nhận là placeholder. Ảnh lấy từ Unsplash (`static/src/img/CREDITS.txt`) và không phải giáo viên hay học viên thật. Không dùng ảnh hoặc nội dung của yola.vn, vì đó là tài sản có bản quyền của bên khác.
- Thử nghiệm trên DB `edu3`. DB `edu` có menu gắn sai cây, còn `edu2` là bản cài dở. Có thể xoá cả hai.

## Git

- Không commit `.pyc`, cache, database dump hay ảnh thật người dùng upload từ filestore. Khi stage chọn đúng file/phạm vi thay đổi, không dùng `git add .`.
- Làm việc trên nhánh riêng, không push thẳng lên `master`.

## Kiểm tra giao diện

Dùng browser tools sẵn có để kiểm tra bản local: đọc hướng dẫn của công cụ, reload sau upgrade/restart, kiểm tra snapshot/DOM và screenshot. Đợt 23/10 đã dùng Chrome kết nối qua browser tools, không cần Chrome headless riêng.

Kiểm tra desktop và mobile 390px, tràn ngang, ảnh tải thành công, tab/filter và console errors. Sau khi thử viewport mobile phải reset về kích thước ban đầu. Không khẳng định đạt FPS cụ thể nếu chưa đo bằng profiler. Khi có nhiều DB phải chọn đúng DB; xem tài liệu bàn giao website.
