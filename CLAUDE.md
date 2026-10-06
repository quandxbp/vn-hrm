# vn-hrm

Odoo 17 HRM cho VNPT, chạy bằng Docker. Kèm addon `edu_landing` (landing page trung tâm tiếng Anh) dùng chung server.

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
  - `vnpt_base`, `vnpt_hrm`, `vnpt_hrm_attendance`, `vnpt_hrm_payroll`: nghiệp vụ HRM.
  - `vnpt_hrm_dashboard`: client action OWL `owl.vnpt_hrm_dashboard`, trang chủ sau khi đăng nhập.
  - `muk_theme/*`: theme backend MuK, đã chỉnh sửa (sidebar, navbar, màu).
  - `edu_landing`: landing page Website, chỉ cần `website` + `website_crm` (Community).
- `required-addons/`: addon Enterprise (`hr_payroll`, license OEEL-1), mount vào `/mnt/enterprise`.
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
