# vn-hrm

Odoo 17 chạy bằng Docker. Hiện dùng cho trung tâm luyện nói tiếng Anh với giáo viên nước ngoài (GVNN): module `edu_gvnn` thay file `TỔNG HỢP_GVNN.xlsx`, kèm `edu_landing` (landing page) dùng chung server. Phần HRM của VNPT là mã cũ, không còn dùng cho GVNN.

> **Trạng thái:** `edu_gvnn` đã làm xong giai đoạn 1-8 và đang chạy trên DB `gvnn` (chưa có dữ liệu, chờ người dùng import file Excel). Đọc [docs/GVNN_PLAN.md](docs/GVNN_PLAN.md) trước khi sửa: có nghiệp vụ đã chốt, bảng đối chiếu với Excel và các phát hiện kỹ thuật. Cập nhật file đó khi nghiệp vụ hoặc tiến độ thay đổi.

## Chạy

```sh
docker compose up -d            # web (odoo:17.0) + db (postgres:15)
docker compose logs -f web
```

- Web: http://localhost:8069. Master password và DB credential nằm trong `config/odoo.conf`.
- `docker compose` có `command: -u vnpt_base`, nên mỗi lần web khởi động lại đều nâng cấp `vnpt_base`.
- Server có nhiều database và `dbfilter` đang trống, nên phải chọn DB bằng `/web/login?db=<tên>` trước khi vào `/`.

## Cấu trúc

- `custom-addons/`: code của dự án (mount vào `/mnt/extra-addons`).
  - `edu_gvnn`: nghiệp vụ GVNN (giáo viên và đơn giá, lớp, học viên, buổi học, thu học phí, kỳ lương, cảnh báo tuần, báo cáo tài chính, import/export Excel). Phụ thuộc `base`, `mail`, `web`, `vnpt_base`; không dùng `hr` hay `account`.
  - `vnpt_hrm_dashboard`: dashboard GVNN (client action OWL `owl.vnpt_hrm_dashboard`, model `edu.dashboard`), trang chủ sau khi đăng nhập. Phụ thuộc `edu_gvnn`.
  - `vnpt_base`: nền dùng chung (đăng nhập, tiêu đề, địa chỉ VN). Còn dùng.
  - Các module HRM cũ (`vnpt_hrm`, `vnpt_hrm_attendance`, `vnpt_hrm_payroll`) đã bị xoá ngày 2026-10-09 theo yêu cầu của người dùng. Còn trong lịch sử git (commit `7083bfa` trở về trước) nếu cần khôi phục.
  - `muk_theme/*`: theme backend MuK, đã chỉnh sửa (sidebar, navbar, màu).
  - `edu_landing`: landing page Website, chỉ cần `website` + `website_crm` (Community).
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

- Ghi đè `website.homepage` (vùng `#wrap`) và footer. Các khối nằm trong `oe_structure` nên vẫn sửa được bằng trình dựng kéo thả.
- Form đăng ký gửi tới `/website/form/crm.lead` và tạo lead. Các trường tự đặt (chương trình, cơ sở) được ghi vào `description` của lead.
- Menu neo (`/#chuong-trinh`, ...) được tạo trong `hooks.py` (`post_init_hook`) và gắn vào `website.menu_id` của từng website, không gắn vào `website.main_menu`. Cách khai báo bằng XML với `eval="obj()..."` không chạy được trên Odoo 17.
- **Nội dung và ảnh đều là mẫu.** Số liệu, tên, lời cảm nhận là placeholder. Ảnh lấy từ Unsplash (`static/src/img/CREDITS.txt`) và không phải giáo viên hay học viên thật. Không dùng ảnh hoặc nội dung của yola.vn, vì đó là tài sản có bản quyền của bên khác.
- Thử nghiệm trên DB `edu3`. DB `edu` có menu gắn sai cây, còn `edu2` là bản cài dở. Có thể xoá cả hai.

## Git

- Không commit file `.pyc`. Repo hiện đang theo dõi 41 file `.pyc` trong `required-addons/hr_payroll`, và chúng luôn hiện là đã thay đổi sau khi chạy Odoo. Khi stage chỉ chọn đúng file của mình, không dùng `git add .`.
- Làm việc trên nhánh riêng, không push thẳng lên `master`.

## Kiểm tra giao diện

Công cụ đọc ảnh không hiển thị được ảnh chụp màn hình trong môi trường này. Thay vào đó, kiểm tra bằng Chrome headless qua DevTools Protocol:

```sh
chrome --headless=new --remote-debugging-port=9333 --remote-allow-origins=* --user-data-dir=<tmp>
```

Sau đó dùng `websocket-client` (Python) để đo kích thước, tương phản và lỗi console, rồi tắt đúng tiến trình Chrome có `--remote-debugging-port=9333` (không tắt Chrome của người dùng).
