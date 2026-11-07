# Kim Academy production trên .128

Cập nhật 07/11/2026 (UTC+7). Đã di chuyển GVNN từ `.105` sang `.128`, giữ nguyên
database, domain, tài khoản, source và phiên bản module. Đọc tài liệu này trước các
hướng dẫn `.105` cũ. Không áp dụng quy trình Công dân số để thay nhầm project.

## Vị trí và kết nối

| Thành phần | Giá trị |
| --- | --- |
| Server / tài khoản SSH | `10.77.160.128` / `Administrator` |
| Hostname đã kiểm chứng | `WIN-I5S839ADRT0` |
| Website / database | https://kimacademy.uk / `kimacademy` |
| Thư mục vận hành | `C:\KimAcademy` |
| Git checkout | `C:\KimAcademy\source`, nhánh `feature/edu-gvnn` |
| Git remote | `https://github.com/quandxbp/vn-hrm.git` |
| Compose chạy thật | `C:\KimAcademy\compose.production.yml` |
| Compose project | `kimacademy128` |
| Config runtime | `C:\KimAcademy\config\odoo.conf` |
| Zalo secret runtime | `C:\KimAcademy\.env.zalo` — không in/copy vào Git |
| Tunnel | Task SYSTEM `KimAcademyTunnel`, thư mục `C:\KimAcademy\cloudflared` |
| Stack startup | Task SYSTEM `KimAcademyStack`, script `operations\start-stack.ps1` |

SSH ED25519 đã xác minh với chủ máy:
`SHA256:cp2o3MbZU+1FFTf68A4jghfAjcHtG01sft+eTe9/Gyc`.
Key đăng nhập local vẫn là key quản trị sẵn có; không copy private key lên server.
File known_hosts tạm từng dùng: `$env:TEMP\vn-hrm-srv128-known-hosts`; có thể mất
sau khi dọn TEMP, cần dựng lại từ host key và đối chiếu fingerprint trước khi dùng.
Shell SSH mặc định là CMD; dùng PowerShell `-EncodedCommand` cho lệnh phức tạp.

Máy .128 đồng thời chạy Công dân số trên cổng 8079. Không stop/recreate container,
volume, image tag hay thay cấu hình Docker/VM của Công dân số trong thao tác GVNN.

## Container, image và volume

| Service | Container | Image đã giữ từ .105 |
| --- | --- | --- |
| web | `kimacademy128-web-1` | `kimacademy-odoo:migrate-b30fe06` |
| db | `kimacademy128-db-1` | `kimacademy-postgres:migrate-b30fe06` |
| zalo-bridge | `kimacademy128-zalo-bridge-1` | `kimacademy-zalo:migrate-b30fe06` |

Volume production có tên cố định, khai báo **external** trong Compose:

- `kimacademy128_postgres-production-data`
- `kimacademy128_odoo-production-data`
- `kimacademy128_zalo-production-data`

Không xóa volume hoặc dùng `down -v`. Các volume không có chữ `production` là bản
thử seed, đã neutralize; không nhầm chúng với dữ liệu đang phục vụ.
`C:\KimAcademy\compose.yml` cũng là cấu hình thử, không dùng để vận hành production.

Odoo chỉ bind `127.0.0.1:8069`. DB không publish cổng host. Config runtime dùng
`proxy_mode=True`, `list_db=False`, `dbfilter=^kimacademy$`; base URL đã đặt
`https://kimacademy.uk` và freeze. Không ghi đè runtime config bằng config Git cũ.

Docker Desktop/Engine trên .128 đã có trước lần migration: Engine 20.10.11,
Compose 2.2.1, Linux VM 2 CPU/2 GB RAM. Không nâng engine hoặc đổi tag `odoo:17.0`,
`postgres:15` chung để chuyển GVNN; đã dùng tag riêng để bảo toàn Công dân số.

## Domain và tự khởi động

Giữ nguyên named tunnel và DNS Kim Academy. Ingress đã kiểm tra chỉ có
`kimacademy.uk -> http://127.0.0.1:8069` và fallback 404.
Connector .105 đã dừng/Disabled trước khi connector .128 được bật.

Task `KimAcademyTunnel` chạy SYSTEM AtStartup, HTTP2, metrics loopback
`127.0.0.1:18128`. Token nằm trong `cloudflared\tunnel.token`, thư mục có ACL riêng
SYSTEM/Administrators. Không in token, nội dung config đầy đủ hoặc log tunnel thô.
Task tự retry khi lỗi; runtime giữ cloudflared 2026.10.0 như nguồn.

Task `KimAcademyStack` chạy SYSTEM sau startup một phút, đợi daemon Docker rồi
`up -d` đúng project. Ba container có restart policy `unless-stopped`.
Chưa reboot toàn máy để nghiệm thu trong lần chuyển này; tác vụ chờ Docker không
thay thế việc Docker Desktop/VM cần sẵn sàng. Cấu hình boot của Docker/VM dùng chung
được giữ nguyên. Không tự reboot máy để thử khi còn Công dân số đang hoạt động.

## Lệnh vận hành đúng project

Chạy PowerShell trên .128:

```powershell
Set-Location C:\KimAcademy
docker compose -p kimacademy128 -f compose.production.yml --profile zalo ps
Get-ScheduledTask -TaskName KimAcademyTunnel,KimAcademyStack |
    Select-Object TaskName,State
Invoke-WebRequest http://127.0.0.1:18128/ready -UseBasicParsing -TimeoutSec 5
Invoke-WebRequest https://kimacademy.uk/web/login -UseBasicParsing -TimeoutSec 20 |
    Select-Object StatusCode
```

Lịch giáo viên cần query `teacher` hoặc đường dẫn edit có token; GET trần
`/weekly-schedule` trả 404 theo thiết kế, không tự kết luận lỗi migration.

Khi phải restart web: lưu cờ AI/video/Zalo/cron; tạm dừng worker và chờ advisory lock
87421/87422/87425 cùng lock gửi Zalo kết thúc. Giữ tiến độ upload và trạng thái yêu cầu
đã gửi; không reset `analysis_started` để bỏ qua timeout. Khôi phục cờ gốc sau health check.

Compose 2.2.1 có thể không tự phát hiện thay đổi tên volume. Nếu đổi image/mount,
kiểm tra `docker inspect ... .Mounts` và cân nhắc `--force-recreate --renew-anon-volumes`
đúng service; named volume dữ liệu phải được giữ nguyên. Không chạy lệnh tái tạo toàn
Docker hoặc project Công dân số để sửa GVNN.

## Source và phát hành tiếp theo

Ứng dụng giữ commit `b30fe06b48df6a417903b4f739cd1ddcf7fda3fd`:
GVNN 17.0.1.17.4, AI 17.0.2.3.2; nút Copy chỉ icon và menu theo role vẫn giữ.
Checkout được chuyển bằng **Git bundle đầy đủ lịch sử**, sau đó đặt lại origin chuẩn.
Không chuyển SSH key quản trị/GitHub cá nhân sang máy mới; chưa cấp deploy key GitHub
mới cho .128. Nếu Git pull cần xác thực, dùng deploy key chỉ đọc được chủ repo cấp hoặc
chuyển Git bundle chứa commit đã duyệt bằng SSH; không đưa token cá nhân vào script.

Source mount read-only vào container. Chạy Odoo upgrade từ **Compose production ở
C:\KimAcademy**, không chạy `docker-compose.yml` trong checkout vì cổng/volume khác.
Trước release phải backup DB + filestore + Zalo volume và ghi full SHA; chỉ upgrade
module đã thay đổi. Migration này không nâng version hoặc tự phân tích lại video.

## Dữ liệu và tích hợp đã đối chiếu

Hai phía khớp sau lần backup cuối: 105 buổi, 74 học viên, 6 giáo viên, 21 lớp,
2 tuần, 157 lượt tham dự, 55 video jobs, 59 AI reports, 16 log Zalo, 192 attachments.
25 attachment lưu file đều có file vật lý, không thiếu file.

Video: 50 done / 5 failed. AI: 41 done / 18 failed. Đây là trạng thái cũ được bảo toàn,
không phải lỗi mới sinh ra khi chuyển; không tự retry yêu cầu mất phản hồi.
AI vẫn `sync`, không bật Batch/Paid Tier. Worker AI/video đã khôi phục True và 23 cron
đã bật lại. OAuth Drive/YouTube và API key giữ nguyên; DB ghi connected, không tạo
video/AI mới chỉ để kiểm thử. Zalo phục hồi credentials + nhóm nhận + ledger, probe
nhóm thực tế thành công; không gửi tin test. Giữ giờ gửi 09:00 UTC+7.

Đã kiểm tra domain HTTPS, trang chủ, đăng nhập, lịch giáo viên, CSS/JS, tunnel ready,
Zalo healthy. Công dân số .128 và gateway Công dân số .105 vẫn trả health/HTTP 200.

## Backup và rollback

Backup nguồn có ACL riêng:
`C:\ProgramData\KimAcademyMigration\to128-20261107` trên .105.
Backup chốt ở thư mục con `final`: `database-final.dump`, `odoo-final.tgz`,
`zalo-final.tgz`, worker flags, source audit và checksum. Đã kiểm tra pg_restore list,
checksum chuyển trực tiếp hai server và đối chiếu dữ liệu sau restore.

Trên .128: `C:\KimAcademy\incoming`, `backups`, `migration-success.json`.
Các file này có DB/credentials/token, không đưa vào repository hoặc máy trung gian.
Đã gỡ key SFTP tạm trên .128 và xóa private key tạm trên .105; key quản trị giữ nguyên.

Nguồn cũ .105 vẫn có repo `C:\inetpub\wwwroot\vn-hrm` và ba volume `vn-hrm_*` nguyên vẹn.
Ba container web/db/Zalo đã stop, restart policy `no`; dịch vụ `Cloudflared` dành Kim
Academy đã stop và Disabled để không chạy song song sau reboot. **Không dừng task
CongDanSoGatewayBootstrap/CongDanSoGatewayTunnel** trên .105.

Rollback phải tạm dừng ghi mới trên .128 và đối chiếu dữ liệu phát sinh sau cutover
trước. Bật lại DB/worker flags/cron của nguồn cũ từ receipt chỉ khi dữ liệu đã đồng bộ;
sau đó chuyển connector, đảm bảo một bên gửi Zalo/AI/YouTube. Không đơn giản bật bản
.105 cũ khi .128 đã nhận dữ liệu mới. Không xóa bản cũ/backup trong phiên migration này.
