# Kết nối server Kim Academy cho phiên làm việc tiếp theo

Cập nhật: **07/11/2026**, giờ Việt Nam (UTC+7).

## Server đang phục vụ production: .128

Kim Academy đã chuyển sang **10.77.160.128 / Administrator**. Source tại
`C:\KimAcademy\source`; Compose thật `C:\KimAcademy\compose.production.yml`, project
`kimacademy128`. Xem [runbook .128](KIMACADEMY_SERVER_128.md) trước khi thao tác.
Host fingerprint ED25519 đã được người dùng đối chiếu trực tiếp:
`SHA256:cp2o3MbZU+1FFTf68A4jghfAjcHtG01sft+eTe9/Gyc`.

**Các lệnh .105 bên dưới giữ lại làm lịch sử và rollback. Không chạy deploy/restart
GVNN trên .105 khi mục tiêu là production hiện tại.** Cầu nối Công dân số trên .105
là hệ thống riêng, vẫn đang phục vụ và không được dừng theo GVNN.

Đọc [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) trước để biết kiến trúc, phiên bản,
tiến độ khôi phục AI và việc chưa được phép chạy lại. Các backup theo ngày bên dưới
là lịch sử; không mặc định đó là lần triển khai mới nhất.

Tài liệu này ghi lại kết nối và trạng thái đã kiểm chứng. Trước khi thay đổi server,
đọc lại yêu cầu hiện tại của người dùng và kiểm tra trạng thái thực tế; không mặc định
các thông tin dưới đây luôn còn đúng.

## Thông tin kết nối

| Mục | Giá trị |
| --- | --- |
| IP nội bộ | `192.168.110.105` |
| SSH port | `22` |
| Tài khoản SSH | `administrator` — **không phải** `Adminstrator` |
| Windows identity đã kiểm chứng | `srv105-qlda\administrator` |
| Hostname | `SRV105-QLDA` |
| Hệ điều hành | Windows Server 2019 Standard, build 17763, x64 |
| Website | https://kimacademy.uk |
| Repo trên server | `C:\inetpub\wwwroot\vn-hrm` |
| Repo local | `D:\Software\vn-hrm` |
| Git remote | `https://github.com/quandxbp/vn-hrm.git` |
| Nhánh | `feature/edu-gvnn` |
| Database production | **`kimacademy`** |

Máy chạy lệnh phải truy cập được mạng nội bộ/VPN tới IP trên. Không mặc định DB
production là `odoo` hoặc `gvnn`; đó là các tên từng dùng ở môi trường khác.

## SSH key và xác minh server

Máy Windows của người dùng đã có key mặc định `~/.ssh/id_ed25519`. Public key tương ứng
đã được thêm trên server vào:

```text
C:\ProgramData\ssh\administrators_authorized_keys
```

File trên chỉ cấp quyền cho Administrators và SYSTEM. **Không chép private key,
mật khẩu, token hoặc nội dung `.env.zalo` vào tài liệu, Git hay log.**

ED25519 host fingerprint đã được người dùng xác minh trực tiếp trên server:

```text
SHA256:cp2o3MbZU+1FFTf68A4jghfAjcHtG01sft+eTe9/Gyc
```

Chạy đoạn sau bằng PowerShell trên máy local. Nó chỉ tin host key nếu fingerprint
khớp giá trị đã xác minh, rồi thử đăng nhập không hỏi mật khẩu:

```powershell
$sshHostKeyFile = Join-Path $env:TEMP 'vn-hrm-srv105-known-hosts'
$expectedFingerprint = 'SHA256:cp2o3MbZU+1FFTf68A4jghfAjcHtG01sft+eTe9/Gyc'

$hostKey = ssh-keyscan -T 10 -t ed25519 192.168.110.105 2>$null
if (!$hostKey) { throw 'Không lấy được SSH host key; kiểm tra mạng và cổng 22.' }
$hostKey | Set-Content -LiteralPath $sshHostKeyFile -Encoding ascii
$fingerprintOutput = ssh-keygen -lf $sshHostKeyFile
if ($LASTEXITCODE -ne 0) { throw 'Không đọc được fingerprint.' }
$actualFingerprint = (($fingerprintOutput -join ' ') -split '\s+')[1]
if ($actualFingerprint -ne $expectedFingerprint) {
    throw 'Fingerprint không khớp. Dừng kết nối và xác minh lại trực tiếp với người dùng.'
}

ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes `
    -o "UserKnownHostsFile=$sshHostKeyFile" administrator@192.168.110.105 hostname
```

Kết quả mong đợi: `SRV105-QLDA`.

Trong môi trường agent, lệnh SSH có thể cần `exec_command` với
`sandbox_permissions="require_escalated"` để truy cập mạng và key của tài khoản
Windows thật. Sandbox từng dùng tài khoản khác và không nhìn thấy key đó.
Không tạo lại key hoặc sửa quyền chỉ vì sandbox không đọc được key hiện có.
Nếu cần quyền thực thi, dùng cơ chế approval của công cụ.

Agent sử dụng công cụ chạy lệnh để mở phiên SSH riêng; không phụ thuộc terminal
SSH do người dùng mở. Không yêu cầu người dùng gửi private key hoặc mật khẩu qua chat.

## Chạy lệnh PowerShell từ xa

Shell SSH mặc định đã kiểm chứng là **cmd.exe**. Với nhiều lệnh PowerShell,
dùng `-EncodedCommand` để tránh lỗi escape dấu nháy, tiếng Việt và dấu chấm phẩy:

```powershell
$remoteScript = @'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-Location 'C:\inetpub\wwwroot\vn-hrm'
whoami
git status --short --branch
git log -1 --oneline
docker compose version
docker compose --profile zalo ps
'@

$encodedScript = [Convert]::ToBase64String(
    [Text.Encoding]::Unicode.GetBytes($remoteScript)
)
ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes `
    -o "UserKnownHostsFile=$sshHostKeyFile" administrator@192.168.110.105 `
    "powershell -NoProfile -EncodedCommand $encodedScript"
```

Đoạn này dùng `$sshHostKeyFile` từ bước xác minh phía trên. Base64 chỉ giải quyết
việc truyền câu lệnh; **không phải mã hóa bảo mật**.

Script dài có thể vượt giới hạn command line của Windows (`The command line is too long`).
Khi đó lưu thành `.ps1` trong thư mục tạm local, dùng `scp` chuyển tới một đường dẫn
tạm riêng trên server, rồi chạy `powershell -NoProfile -File <đường-dẫn>` qua SSH.
Không thay ExecutionPolicy mặc định để vượt lỗi. Nếu chính sách chặn, kiểm tra nguyên nhân.

Ví dụ chuyển một script đã chuẩn bị:

```powershell
scp -o BatchMode=yes -o StrictHostKeyChecking=yes `
    -o "UserKnownHostsFile=$sshHostKeyFile" `
    $localScriptFile administrator@192.168.110.105:C:/Windows/Temp/kim-task.ps1
if ($LASTEXITCODE -ne 0) { throw 'Chuyển script thất bại.' }

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes `
    -o "UserKnownHostsFile=$sshHostKeyFile" administrator@192.168.110.105 `
    'powershell -NoProfile -File C:\Windows\Temp\kim-task.ps1'
```

`$localScriptFile` phải trỏ tới script đã được tạo và kiểm tra cho công việc hiện tại.

## Docker và các dịch vụ

| Thành phần | Trạng thái đã kiểm chứng |
| --- | --- |
| Docker Desktop | `4.3.0.71786` |
| Docker CLI / Linux Engine | `20.10.11`, API `1.41` |
| Docker Compose của Administrator | **`v5.6.1`** |
| Buildx | `v0.7.1` |
| Compose project | `vn-hrm` |
| Web container | `vn-hrm-web-1`, image `odoo:17.0` |
| DB container | `vn-hrm_db_1`, image `postgres:15` |
| Zalo bridge | `vn-hrm-zalo-bridge-1`, image `vn-hrm-zalo-bridge:latest` |

Tên container có thể đổi khi recreate. Lấy ID hiện tại bằng `docker compose ps -a -q <service>`
trước khi dùng `docker exec` hoặc `docker cp`; không phụ thuộc mãi vào các tên trên.

Compose mới được cài cho tài khoản Administrator tại:

```text
%USERPROFILE%\.docker\cli-plugins\docker-compose.exe
```

Bản hệ thống cũ `2.2.1` vẫn được giữ tại:

```text
C:\Program Files\Docker\cli-plugins\docker-compose.exe
```

Dùng **`docker compose`**, không dùng `docker-compose` để tránh gọi nhầm bản cũ.
Tài khoản khác hoặc Windows service có thể không thấy plugin mới; luôn kiểm tra phiên bản.
Docker Desktop không được hãng hỗ trợ trên Windows Server. Không tự nâng Desktop/Engine
lên bản mới trên hệ điều hành này; lần trước chỉ nâng Compose và giữ Engine đang chạy.

Các lệnh kiểm tra an toàn trên server:

```powershell
Set-Location 'C:\inetpub\wwwroot\vn-hrm'
git status --short --branch
docker compose version
docker compose --profile zalo ps
docker compose exec -T db psql -U odoo -d kimacademy -c `
    "SELECT name,state,latest_version FROM ir_module_module WHERE name IN ('edu_gvnn','edu_landing','edu_zalo','vnpt_hrm_dashboard') ORDER BY name"
```

Trước khi restart/deploy, kiểm tra yêu cầu hiện tại, dữ liệu local và backup.
Các lệnh vận hành khi công việc đã yêu cầu restart tương ứng:

```powershell
docker compose restart web
docker compose --profile zalo restart zalo-bridge
```

Zalo image đã build thành công bằng legacy builder vì Buildx hiện quá cũ:

```powershell
$env:DOCKER_BUILDKIT = '0'
docker build -t vn-hrm-zalo-bridge:latest services/zalo-bridge
if ($LASTEXITCODE -ne 0) { throw 'Build Zalo bridge thất bại.' }
docker compose --profile zalo up -d --no-build --no-deps zalo-bridge
```

Không cần rebuild/restart bridge chỉ để thay cấu hình giờ gửi hoặc nhóm nhận trong Odoo.

## Trạng thái code và dữ liệu lúc bàn giao

- Đã kiểm tra ngày 03/11: local/server cùng nhánh `feature/edu-gvnn`; production đã
  deploy Batch 2.3.1 tại `cc4f97bd2a5c0cfc3fadc7fb858b50ffc327a328`.
- Không còn thay đổi code ứng dụng chưa commit ở hai phía. Ba override tài liệu cũ
  đã giữ trong backup/stash tại `backups\ai-batch-20261103-085608` trước khi đồng bộ.
  Khi pull lần sau vẫn kiểm tra diff thực tế, không reset hoặc ghi đè mù.
- `edu_zalo` production **17.0.1.4.0**, `edu_session_review` **17.0.2.3.1**.
  Bảng đầy đủ và trạng thái hàng đợi ở [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md).
- Local DB `kimacademy` là bản sao neutralized, worker gửi thật tắt. `gvnn` và `odoo`
  trong các ghi chú cũ không phải tên DB production hiện tại.
- `import_data/` chứa Excel dữ liệu thật, đã được ignore; không commit/push như source.
  Git không đồng bộ DB/filestore. Không restore local đè production khi chỉ cập nhật code.
- Tuần 103 đã nhập 52 buổi / 79 lượt tham dự; tuần 104 đã nhập 53 buổi / 79 lượt tham dự.
  Người dùng xác nhận **MOSHOOD = SMITH**; không tạo giáo viên trùng khi import.
- DB còn đánh dấu `vnpt_hrm_attendance` installed nhưng thiếu source addon. Không tự
  uninstall hoặc xóa dữ liệu để che cảnh báo.

## Zalo đã cấu hình

- Tài khoản: **Kim Academy - Học Vụ**; đã đăng nhập và bridge connected.
- Nhóm nhận mặc định và nhóm đã xác nhận:
  **KIMACADEMY - TRẢI NGHIỆM NÓI ONLINE**.
- Gửi tự động đang bật, **09:00 mỗi ngày theo Asia/Ho_Chi_Minh**; cấu hình hiện tại
  cho phép gửi bù an toàn trong **6 giờ**, chỉ cùng ngày. Có retry/monitor và activity
  cảnh báo; xem [ZALO_TLS_COMPATIBILITY.md](ZALO_TLS_COMPATIBILITY.md).
- Form có ô `send_hour` và nút **Chọn nhóm theo tên**. Nhập tên không tự đổi nhóm mặc định;
  chọn nhóm rồi **Xác nhận nhóm nhận**. Đổi sang nhóm chưa xác nhận sẽ tắt tự động gửi.
- URL cấu hình: https://kimacademy.uk/web?db=kimacademy#id=1&model=edu.zalo.config&view_type=form
- Không bấm gửi thử, gọi `/messages`, chạy cron gửi hoặc đổi nhóm nếu công việc hiện tại
  không yêu cầu. Giữ nguyên lịch sử gửi và cơ chế chống trùng.
- Khóa nội bộ nằm trong `.env.zalo` và system parameters của DB. Phiên đăng nhập, nhóm nhận
  và sổ chống trùng nằm trong volume **`vn-hrm_zalo-bridge-data`**. Giữ và backup volume này
  cùng dữ liệu vận hành; không dùng `down -v` hoặc xóa volume để sửa lỗi kết nối.
- Các bài kiểm tra Zalo dùng bridge giả, không dùng gửi tin thật để test. Kết quả 16/16
  trong bản bàn giao 26/10 là kết quả lịch sử trước các bản sửa reliability ngày 31/10.
- Chi tiết chức năng: [ZALO_SCHEDULE.md](ZALO_SCHEDULE.md).

## Backup và tài liệu vận hành trên server

Thư mục chung ngoài repo:

```text
C:\ProgramData\KimAcademyDeploy
```

| Đường dẫn tương đối | Nội dung |
| --- | --- |
| `OPERATIONS.txt` | Ghi chú Docker/Compose và vận hành |
| `manual-success.json` | Metadata lần deploy code trước |
| `backups\20261026-133726` | DB và filestore trước deploy `f2b9495` |
| `backups\zalo-20261026-135118` | DB/filestore trước cài Zalo |
| `week103-import\backup-20261026-141238` | DB trước import tuần 103 |
| `week103-import\import-report.json` | Đối chiếu các buổi đã import |
| `zalo-config-update\backup-20261026142042` | DB và source addon trước đổi giờ gửi/nhóm nhận |
| `zalo-config-update\RESULT.txt` | Kết quả triển khai cấu hình Zalo |
| `docker-compose.runtime.yml` | Snapshot web/db cũ, chỉ dùng dự phòng; **không chứa Zalo bridge** |

Backup mới hơn của tuần 104 và AI 2.2.3/2.2.4 xem mục backup trong
[PROJECT_HANDOFF.md](PROJECT_HANDOFF.md).

Backup chứa dữ liệu thật và có thể chứa secrets trong DB; giữ riêng trên server,
không upload công khai hoặc đưa vào Git. Kiểm tra file thực tế và metadata trước restore.

`deploy/windows/Deploy.ps1` trong repo chưa được cập nhật cho mọi tình huống phát sinh:
Compose cũ từng không copy được file từ service đã dừng. `docker cp <container-id>:<path> <dest>`
đã giải quyết việc đó. Script cũng chưa tự bao gồm backup volume Zalo. Đọc và điều chỉnh
trước khi dùng cho production; không tự bật GitHub runner hay auto-deploy.

## Lỗi từng gặp

- **`Permission denied (publickey,password,keyboard-interactive)`**: kiểm tra đúng tài khoản
  `administrator`, đúng Windows user local và key hiện có; không gửi mật khẩu vào chat.
- **Host key chưa được biết**: chạy bước đối chiếu fingerprint ở trên, không tắt strict checking.
- **Git `dubious ownership` trong sandbox local**: với lệnh chỉ đọc, có thể dùng
  `git -c safe.directory=D:/Software/vn-hrm ...`; không đặt `safe.directory=*`.
- **PowerShell coi stderr của Docker là lỗi**: với tác vụ dài dùng
  `Start-Process docker -WindowStyle Hidden -Wait -PassThru` và
  `-RedirectStandardOutput` / `-RedirectStandardError` tới hai file riêng, rồi kiểm tra `ExitCode`.
  Đọc log có giới hạn; không in token, QR hoặc thông tin phiên đăng nhập.
- **Unicode trong log bị lỗi**: script Python có thể in JSON với `ensure_ascii=True`;
  giải mã để đọc khi cần. Không sửa tên trong DB dựa trên log bị lỗi encoding.
- **`docker cp` tạo file root-owned trong `/tmp`**: khi dọn bản tạm do chính tác vụ tạo,
  có thể cần `docker exec --user root ... rm -- <đường-dẫn-tạm-chính-xác>`.
  Không áp dụng với file nguồn, DB hoặc volume dữ liệu thật.

## Gợi ý bắt đầu phiên sau

Người dùng có thể yêu cầu:

> Đọc `docs/SERVER_CONNECTION_HANDOFF.md`, kiểm tra SSH tới server Kim Academy và
> kiểm tra trạng thái repo/dịch vụ trước khi tiếp tục công việc tôi yêu cầu.

Sau khi kết nối, đọc thêm [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md)
và [WINDOWS_DEPLOY.md](WINDOWS_DEPLOY.md) nếu công việc liên quan deploy. Một số trạng thái
trong tài liệu cũ là môi trường local trước khi production được cập nhật; ưu tiên trạng thái
server kiểm tra được ở phiên hiện tại.
