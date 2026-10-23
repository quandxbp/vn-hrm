# Auto deploy Kim Academy qua GitHub Actions

## Trạng thái

Đã chuẩn bị workflow `.github/workflows/deploy-windows.yml` và worker `deploy/windows/Deploy.ps1`.
Chưa cài runner, chưa cấu hình DB hoặc chạy deploy trên server thật.
Workflow chỉ chạy sau khi đặt repository variable **KIM_DEPLOY_ENABLED=true**.

Đã kiểm tra cú pháp PowerShell và mô phỏng Git/Docker/HTTP cho các nhánh: Plan, backup trước migration,
deploy thành công, bỏ qua commit đã deploy, migration lỗi giữ web dừng, pending chặn chạy lại và RetryFailed.
Chưa kiểm chứng end-to-end với Docker hoặc GitHub runner trên Windows Server thật.

Môi trường người dùng cung cấp: Windows Server 2019 Standard x64, build 17763, Docker Desktop.
GitHub runner hỗ trợ Windows Server 2019; Docker Desktop không được Docker hỗ trợ chính thức trên Windows Server.
Stack này cần Linux containers (`odoo:17.0`, `postgres:15`). Cần kiểm tra engine hiện có hoạt động
và runner truy cập được engine trước khi bật deploy. Phương án triển khai được hỗ trợ tốt hơn là
chạy stack trên Linux VM; bộ script này dành cho môi trường Windows có sẵn Docker CLI/Compose hoạt động.

## Luồng chạy

Push lên `feature/edu-gvnn` → GitHub Actions giao job cho Windows runner mang label `kim-production`.
Runner gọi worker đã cài bên ngoài checkout, không dùng `actions/checkout` trên thư mục production.
Worker:

1. Khóa để không chạy hai bản deploy cùng lúc; từ chối checkout sai nhánh, có sửa đổi local hoặc lịch sử bị phân nhánh.
2. Fetch GitHub và chốt commit mới nhất của nhánh. Nếu commit và cấu hình đã deploy thành công thì bỏ qua.
   Lần đầu vẫn deploy ngay cả khi HEAD đã bằng remote. Job cũ đang đợi có thể deploy commit mới nhất, không cố chạy lại commit cũ.
3. Kiểm tra Linux Docker engine, Compose, DB và các module đã cài.
4. Ghi `pending.json`, dừng **web**, giữ **db** chạy.
5. Sao lưu PostgreSQL bằng `pg_dump -Fc`, sao lưu filestore của DB tương ứng. Chỉ tiếp tục khi cả hai thành công.
6. Fast-forward checkout tới commit đã chốt.
7. Chạy Odoo một lần trong container riêng để `-u` các module cấu hình, HTTP và cron tắt.
8. Tạo lại web container, chờ trang đăng nhập của đúng DB trả 200 và có input login.
9. Ghi `success.json`, xóa pending; log và backup được giữ bên ngoài repo.

Có downtime từ bước 4 đến hết bước 8; thời gian phụ thuộc dung lượng backup và migration.
Không có thao tác `down -v`, không reset checkout, không tự cài module mới, không nâng cấp tất cả module bằng `-u all`.
Nếu backup/migration/health check lỗi sau khi dừng web: web được giữ dừng và lần deploy tiếp theo bị chặn bởi pending.
Không tự rollback code vì DB có thể đã thay đổi schema.

## Cài một lần trên server

Thực hiện trong tài khoản Windows sẽ chạy runner. Cần Git, Windows PowerShell 5.1, Docker Compose v2,
repo production đã clone, DB thực đã được restore/cài đặt và website đang chạy.
Repo phải ở đúng nhánh và không có thay đổi local. Đường dẫn state/backup phải ngoài repo.
Ví dụ đường dẫn dưới đây cần thay theo server thực tế, không mặc định DB trên server là `odoo` hay `gvnn`.

```powershell
docker info --format '{{.OSType}}' # phải là linux
docker compose version
Set-Location D:\Apps\vn-hrm
git branch --show-current
git status --short
docker compose ps

New-Item -ItemType Directory -Path C:\ProgramData\KimAcademyDeploy -Force
Copy-Item deploy\windows\Deploy.ps1 C:\ProgramData\KimAcademyDeploy\Deploy.ps1
Copy-Item deploy\windows\config.example.json C:\ProgramData\KimAcademyDeploy\config.json
notepad C:\ProgramData\KimAcademyDeploy\config.json
```

Chỉnh `RepoPath`, `Database`, `BackupPath`, `HealthUrl`; `Database` và tham số `db=` trong URL phải trùng nhau.
`Modules` phải liệt kê các module đã cài cần tự upgrade. Với thay đổi website hiện tại, dùng `["edu_landing"]`.
Nếu server cũng chạy nghiệp vụ GVNN và muốn cập nhật cả phần đó, dùng
`["edu_landing", "edu_gvnn", "vnpt_hrm_dashboard"]` sau khi kiểm tra chúng đã installed trên DB.
Worker không tự suy luận danh sách module phụ thuộc từ diff; thêm module khi mở rộng phạm vi deploy.
`PostgresUser` mặc định `odoo`, khớp Compose hiện tại.
Script dùng filestore `/var/lib/odoo/.local/share/Odoo/filestore/<Database>` theo `config/odoo.conf` hiện tại.
Nếu server dùng Compose override, project name khác, data_dir khác hoặc Docker context từ xa, phải điều chỉnh worker trước.
Không sử dụng worker này cho repo triển khai nhiều DB đồng thời mà chưa bổ sung nâng cấp/backup từng DB.

Kiểm tra Git dưới chính tài khoản runner: `git fetch origin` phải thành công không cần nhập mật khẩu.
Repo public có thể đọc ẩn danh; repo private dùng deploy key chỉ đọc hoặc Git Credential Manager của tài khoản đó.
Không lưu token/mật khẩu trong JSON hoặc workflow. Nếu gặp dubious ownership, cấu hình safe.directory cho đúng repo
và đúng tài khoản; không dùng wildcard `*`.

```powershell
# Chỉ fetch, kiểm tra nhánh, báo kế hoạch; không dừng dịch vụ hoặc sửa DB.
& C:\ProgramData\KimAcademyDeploy\Deploy.ps1 -ConfigPath C:\ProgramData\KimAcademyDeploy\config.json -Plan

# Deploy thử có backup, downtime và migration thật. Chạy khi đã xác nhận config.
& C:\ProgramData\KimAcademyDeploy\Deploy.ps1 -ConfigPath C:\ProgramData\KimAcademyDeploy\config.json
```

Nếu chính sách PowerShell chặn script, xử lý theo chính sách máy (ví dụ ký script/RemoteSigned được quản trị viên cho phép).
Worker không tự thay ExecutionPolicy.

## Cài GitHub runner

1. Mở repository → **Settings → Actions → Runners → New self-hosted runner**, chọn Windows x64.
2. Chạy các lệnh download/giải nén/config do GitHub hiển thị trên server, đặt runner ở ngoài repo production,
   ví dụ `C:\actions-runner`. Token đăng ký chỉ nhập trực tiếp trên server, không đưa vào Git hay chat.
3. Thêm label **kim-production**, giữ các label mặc định `self-hosted`, `Windows`, `X64`.
4. Chạy thử `run.cmd` dưới tài khoản có quyền Git/Docker, sau đó cấu hình Windows service nếu cần chạy khi đăng xuất.
   Với Docker Desktop, phải kiểm chứng Docker engine còn hoạt động và truy cập được dưới tài khoản service khi đăng xuất/reboot;
   chỉ cài runner service không làm Docker Desktop tự có mặt trong phiên service. Không mặc định LocalSystem dùng được engine/credential.
5. Runner phải hiện **Idle** trên GitHub. Tạo Actions repository variable `KIM_DEPLOY_ENABLED` = `true` sau khi deploy thử thành công.
6. Push commit lên `feature/edu-gvnn` sẽ tự deploy. Sau khi workflow đã có trên default branch,
   có thể dùng **Actions → Deploy Kim Academy → Run workflow**, chọn nhánh `feature/edu-gvnn`.

Repository hiện được ghi nhận là public trong tài liệu dự án. GitHub khuyến cáo không đặt self-hosted runner trên repo public.
Ưu tiên repo deploy private/giới hạn quyền truy cập trước khi gắn runner vào production. Workflow này chỉ nhận push đúng nhánh,
không chạy pull_request/pull_request_target; điều đó không thay thế việc kiểm soát mọi workflow khác có quyền sử dụng runner.
Chỉ người tin cậy được push/sửa workflow; label runner không phải ranh giới phân quyền.

## Xử lý lỗi và vận hành

- Xem job log trên Actions và `StatePath\deploy-*.log`; các file này có thể chứa thông tin vận hành, giữ riêng trên server.
- `BackupPath\<timestamp>-<commit>\` chứa `database.dump`, `filestore.tgz`, `deployment.json`.
  Backup có dữ liệu thật, không upload làm artifact public và không commit vào Git.
- Dung lượng log/backup không tự xóa; cần chính sách lưu giữ và cảnh báo dung lượng của server.
- Khi có `pending.json`, đọc lỗi trước. Nếu sửa được lỗi và muốn tiếp tục upgrade, chạy worker với `-RetryFailed`.
  Không xóa pending để bỏ qua chẩn đoán. GitHub workflow không tự truyền tùy chọn retry này.
- Khi cần rollback: dừng web, restore **cùng bộ** database và filestore từ backup, đưa code về PreviousCommit trong metadata,
  rồi mới khởi động lại. Cần diễn tập restore trên DB/volume riêng trước khi dựa vào backup cho production.
- Khi sửa `Deploy.ps1`, phải kiểm tra và copy lại vào `C:\ProgramData\KimAcademyDeploy`;
  worker đang chạy không tự ghi đè chính nó khi pull. Commit thay đổi Compose/config cần được review vì có thể ảnh hưởng hạ tầng.
- Compose hiện có `command: -u vnpt_base`: web vẫn chạy lệnh đó khi khởi động. Worker chỉ quản lý module trong `Modules`;
  `vnpt_base` vẫn có thể được upgrade thêm do cấu hình gốc này.
- Đây là kiểm tra HTTP cơ bản; không thay thế kiểm tra đăng nhập nghiệp vụ, ảnh hoặc kiểm tra tải sau deploy.
- Nội dung được biên tập ở Kim Website nằm trong DB/filestore **trên server**, không phải Git.
  Pull/upgrade giữ nội dung đã sửa, không đồng bộ album/học viên/giáo viên từ máy local lên server.
  Chuyển nội dung local lần đầu cần backup/restore riêng, không ghi đè DB production mỗi lần push.

## Tài liệu chính thức

- [Docker Desktop và Windows Server](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/windowsfaqs/)
- [Docker Compose run](https://docs.docker.com/reference/cli/docker/compose/run/)
- [GitHub runner: hệ điều hành được hỗ trợ](https://docs.github.com/en/actions/reference/runners/self-hosted-runners)
- [Cài runner dưới Windows service](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/configure-the-application)
- [Bảo vệ self-hosted runner](https://docs.github.com/en/actions/reference/security/secure-use)
