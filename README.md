# Kim Academy / vn-hrm

Ứng dụng Odoo 17 Community cho trung tâm tiếng Anh: quản lý giáo viên nước ngoài,
học viên, lịch học, điểm danh, học phí, lương; website Kim Academy; gửi lịch Zalo;
chuyển video Google Drive lên YouTube và nhận xét buổi học bằng Gemini.

## Bắt đầu phiên làm việc mới

1. Đọc [bàn giao hiện trạng](docs/PROJECT_HANDOFF.md), đặc biệt mục **Việc chưa hoàn tất**.
2. Nếu cần production, đọc [hướng dẫn SSH và server](docs/SERVER_CONNECTION_HANDOFF.md).
3. Kiểm tra Git, đúng database và các worker trước khi sửa hoặc deploy. Không dựa vào
   số liệu trong các bản bàn giao cũ để quyết định gửi lại video/tin nhắn.

| Môi trường | Địa chỉ / vị trí | Database |
| --- | --- | --- |
| Production | https://kimacademy.uk; Windows `192.168.110.105`; `C:\inetpub\wwwroot\vn-hrm` | `kimacademy` |
| Local hiện tại | http://localhost:8069; `D:\Software\vn-hrm` | `kimacademy`, bản sao **neutralized** |
| Git | `https://github.com/quandxbp/vn-hrm.git`, nhánh `feature/edu-gvnn` | Source, không chứa DB/filestore |

Trạng thái được kiểm tra ngày **03/11/2026 (UTC+7)**. Production đã chạy bản sửa
upload AI `4bedad3`, module `edu_session_review` **17.0.2.2.4**. Việc khôi phục AI
còn đang chạy và có các báo cáo timeout chưa được phép phân tích lại; xem bàn giao.
Push Git và deploy Odoo là hai bước riêng.

## Bản đồ code

| Thư mục | Vai trò |
| --- | --- |
| `custom-addons/edu_gvnn` | Nghiệp vụ học viên, giáo viên, lớp, tuần, buổi học, điểm danh, học phí, lương, import/export; lịch giáo viên `/weekly-schedule` |
| `custom-addons/edu_video` | OAuth Drive/YouTube, tải/upload từng phần, ảnh bìa, playlist, worker và cache |
| `custom-addons/edu_session_review` | Hàng đợi Gemini, kiểm tra kết quả, báo cáo AI giáo viên và cảnh báo học sinh |
| `custom-addons/edu_zalo` | Cấu hình nhóm nhận, lịch gửi, biên nhận và cảnh báo vận hành Zalo |
| `services/zalo-bridge` | Dịch vụ Node/Zalo; volume riêng giữ phiên đăng nhập và sổ chống gửi trùng |
| `custom-addons/edu_landing` | Trang chủ, nội dung website, form tư vấn CRM, giao diện `/web/login` |
| `custom-addons/vnpt_hrm_dashboard` | Dashboard GVNN bằng OWL |
| `custom-addons/vnpt_base`, `custom-addons/muk_theme` | Nền dùng chung và theme backend |
| `config`, `docker-compose.yml` | Odoo, PostgreSQL 15, mount/volume; cấu hình phải kiểm tra theo môi trường |
| `deploy/windows`, `.github/workflows/deploy-windows.yml` | Bộ triển khai Windows; không mặc định auto-deploy đã được bật |
| `scripts/gvnn_checks`, `scripts/ops` | Kiểm tra nghiệp vụ và công cụ đọc trạng thái vận hành |

Các thư mục `artifacts/`, `import_data/`, DB dump, OAuth JSON, `.env.zalo` và volume
là dữ liệu vận hành riêng, không đưa lên Git. Không chia sẻ token giáo viên, key Gemini
hay refresh token trong log/tài liệu.

## Chạy local

```powershell
Set-Location 'D:\Software\vn-hrm'
docker compose up -d web db
docker compose ps
```

Mở `http://localhost:8069/web/login?db=kimacademy`. Nếu máy mới chưa có DB,
source không tự khôi phục dữ liệu: cần restore DB **và filestore** từ backup được cấp,
hoặc tạo một DB thử nghiệm riêng. Không dùng DB trống thay cho DB vận hành.
Giữ local neutralized và tắt gửi Zalo/upload/AI; kiểm tra trước khi khởi động bản sao.
Không mang credential production sang local để thử chức năng.

Compose hiện khởi động web với `-u vnpt_base`; restart web không tự upgrade tất cả addon
đã sửa. Thay model/view cần nâng cấp đúng module trên đúng DB; xem quy trình bàn giao.

## Tài liệu theo chức năng

- [Hiện trạng và việc tiếp theo](docs/PROJECT_HANDOFF.md)
- [SSH, Docker và deploy an toàn](docs/SERVER_CONNECTION_HANDOFF.md)
- [Nghiệp vụ và quy tắc học phí/lương](docs/GVNN_PLAN.md)
- [Website và nội dung](docs/WEBSITE_HANDOFF.md), [nội dung trang chủ](docs/KIM_ACADEMY_NOI_DUNG_TRANG_CHU.md)
- [OAuth Google](docs/GOOGLE_VIDEO.md), [video/YouTube](docs/VIDEO_AUTOMATION.md)
- [Nhận xét AI và lỗi đã xử lý](docs/SESSION_AI_REVIEW.md)
- [Lịch Zalo](docs/ZALO_SCHEDULE.md), [TLS và cơ chế phục hồi](docs/ZALO_TLS_COMPATIBILITY.md)
- [Bộ triển khai Windows](docs/WINDOWS_DEPLOY.md)

Các `SESSION_HANDOFF_2026-10-*.md` là lịch sử theo ngày. Khi mâu thuẫn, ưu tiên
`PROJECT_HANDOFF.md` và trạng thái thực tế vừa kiểm tra.
