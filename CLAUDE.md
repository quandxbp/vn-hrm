# Hướng dẫn làm việc với vn-hrm / Kim Academy

Đọc [README.md](README.md), rồi [docs/PROJECT_HANDOFF.md](docs/PROJECT_HANDOFF.md)
trước khi sửa code hoặc vận hành. Đây là tài liệu hiện trạng ngày 03/11/2026;
các `SESSION_HANDOFF_2026-10-*.md` là lịch sử, không phải trạng thái triển khai hiện tại.

## Môi trường

- Odoo 17 Community, PostgreSQL 15, Docker Compose; nhánh `feature/edu-gvnn`.
- Production: `https://kimacademy.uk`, DB **kimacademy**, repo
  `C:\inetpub\wwwroot\vn-hrm`, SSH `administrator@192.168.110.105`.
  Kết nối/fingerprint: [docs/SERVER_CONNECTION_HANDOFF.md](docs/SERVER_CONNECTION_HANDOFF.md).
- Local: `D:\Software\vn-hrm`, `http://localhost:8069`, DB **kimacademy** neutralized.
  Giữ tác vụ gửi thật tắt; source Git không chứa DB/filestore/credential.
- Không coi push Git là deploy. Khi thay model/view phải upgrade đúng addon trên đúng DB.
  Không tự bật runner/auto-deploy; đọc quy trình pause/checkpoint trong bàn giao mới.

## Phạm vi code

- `edu_gvnn`: học viên, giáo viên, lịch/điểm danh, học phí/lương, import/export.
- `edu_video`: Drive → YouTube, upload nhiều phần, thumbnail/playlist.
- `edu_session_review`: AI nội dung/chất lượng buổi học, thang 10 và cảnh báo học sinh.
- `edu_zalo` + `services/zalo-bridge`: gửi lịch, phiên Zalo và sổ chống gửi trùng.
- `edu_landing`: trang chủ/login, website và form tư vấn CRM.
- `vnpt_hrm_dashboard`: dashboard GVNN OWL; `vnpt_base` + `muk_theme`: nền/theme.
- Không còn vận hành bộ HRM cũ. `required-addons/` vẫn được mount vào `/mnt/enterprise`;
  không thêm dependency Enterprise không cần thiết.

## Quy tắc nghiệp vụ/vận hành cần giữ

- MOSHOOD trong Excel là **SMITH**, người dùng đã xác nhận; không tạo giáo viên trùng.
- Giữ khóa buổi/điểm danh và đơn giá sau chốt lương. Không bỏ khóa chỉ để sửa UI.
- Phần video 1 dùng field trên session; các phần sau dùng `edu.session.recording.part`.
- Tên học sinh trên ảnh bìa chỉ áp dụng **video mới**; không backfill video cũ.
- Không dùng gửi tin Zalo/upload YouTube thật để kiểm thử khi chưa được yêu cầu.
- Inference đã gửi nhưng mất phản hồi: không tự reset `analysis_started` hoặc tạo lượt mới.
  Quyền phân tích lại báo cáo 10 chỉ cho **một lần**, bản thay thế là 46. Báo cáo 32
  đã được phép một lượt thay thế qua Batch, còn 38 chưa có quyền chạy lại. Đọc receipt
  trong bàn giao trước khi tạo yêu cầu; không hỏi lặp quyền đã cấp.
- Trước restart/deploy, pause worker và đợi advisory lock/network checkpoint; không kill
  yêu cầu AI/video đang chạy. Giữ nguyên retry ledger, volume, backup và lịch sử lỗi.
- Không uninstall module thiếu source để che log, không restore local đè production.

## Kỹ thuật

- Thay đổi module có view kế thừa phải khai báo dependency tương ứng trong `depends`.
- Odoo compute stored có `default` có thể không recompute lúc create: đặt mặc định trong
  hàm compute nếu cần. Compute không lưu liên quan kỳ lương cần invalidate cache đúng chỗ.
- Odoo lưu JSON list rỗng thành False; so roster bằng `(roster_snapshot or [])`.
- `edu.student` chuẩn hóa tên uppercase. Console Windows lỗi Unicode không phải dữ liệu DB hỏng.
- XML view cập nhật bằng ORM cần signal registry/cache để process web thấy thay đổi.
- Theme/SCSS dùng biến Odoo (`$o-brand-primary`, `$o-gray-*`, `$o-view-background-color`).
  `min()`/`max()` trộn đơn vị cần bọc `unquote(...)`; tránh `@import url(...)` Google Fonts
  trong SCSS. Kiểm tra bundle không có `css_error_message`.
- Chart.js: dùng `loadBundle('web.chartjs_lib')` có sẵn, không tải CDN.
- Màn hình cấu hình nội dung website mới đặt dưới `edu_landing.menu_kim_website` (Kim Website).
- Kiểm tra UI ở desktop và mobile 390px; kiểm tra tràn ngang, ảnh/tab và console. Dùng
  browser tools được cung cấp, đọc hướng dẫn công cụ trước khi thao tác.
- PowerShell là shell local; SSH server mặc định CMD, dùng PowerShell EncodedCommand cho
  script phức tạp. Git Bash cần `MSYS_NO_PATHCONV=1` với đường dẫn Linux trong Docker.

## Kiểm tra và Git

- Script đọc trạng thái, không gửi API: `scripts/ops/inspect_ai_reviews.py`;
  cách chạy trong `docs/PROJECT_HANDOFF.md`.
- Test nghiệp vụ: `scripts/gvnn_checks/README.md`; test addon trong thư mục `tests`.
  Dùng DB thử/clone neutralized và mock mạng. Không coi số test lịch sử là vừa chạy lại.
- Không stage toàn repo bằng `git add .`; chọn file đúng phạm vi và xem staged diff.
- Không commit DB/filestore, Excel, `artifacts/`, `.env.zalo`, OAuth JSON, API key,
  private key hoặc URL chứa token giáo viên. Không log toàn bộ provider response.
- Không force push hoặc push thẳng `master`. Bảo toàn thay đổi local/server chưa commit.
- Với dubious ownership dùng `git -c safe.directory=D:/Software/vn-hrm ...` theo repo;
  không cấu hình wildcard `safe.directory=*`.
