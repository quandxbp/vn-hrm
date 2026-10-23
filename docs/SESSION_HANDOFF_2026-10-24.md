# Bàn giao phiên GVNN và Zalo — 24/10/2026

## Trạng thái hiện tại

- Repo `D:\Projects\vn-hrm`, nhánh `feature/edu-gvnn`.
- Odoo 17 chạy Docker tại `http://localhost:8069`; DB nghiệp vụ local là **`gvnn`**.
  Đã kiểm tra lại: hiện chỉ còn DB này, không mặc định DB `odoo` trong ghi chú cũ còn tồn tại.
- Module đã cài: `edu_gvnn` **17.0.1.1.0**, `edu_zalo` **17.0.1.2.0**,
  `edu_landing` **17.0.1.7.0**.
- Bridge Zalo đã đăng nhập QR và gửi thử thành công vào nhóm thử do người dùng chọn.
  Nhóm nhận, danh xưng, link học và dữ liệu nghiệp vụ nằm trong DB; không có trong Git.
- **Tự động gửi lúc 12:00 đang tắt.** Chưa chuyển sang nhóm vận hành chính thức.
- Chưa triển khai các thay đổi này lên server public. Push Git không đồng nghĩa đã deploy.

## List view buổi học

- Cột Thứ: badge nhỏ 24px, bo 6px, nền nhẹ và chấm màu.
  MON xanh dương, TUE tím, WED cam, THU xanh ngọc, FRI hồng, SAT xám, SUN xanh lá.
- Cột Ngày: chỉ màu chữ theo Thứ, không nền/viền/chấm badge.
- Cột Loại buổi: `optional="hide"`, mặc định ẩn, vẫn có thể bật lại trong bộ chọn cột.
- Widget và CSS ở `edu_gvnn/static/src/fields/weekday_badge.*`.
- Nút **Gửi lịch hôm nay** trên list gọi `edu.session.action_send_today_zalo` trực tiếp.
  Không mở cấu hình, không cần chọn dòng, không lấy ngày từ bộ lọc hay màn hình preview.
  Ngày được tính theo `Asia/Ho_Chi_Minh`; gửi xong hiện thông báo kết quả.
  Chỉ Quản lý GVNN thấy và dùng được nút.

## Mẫu Zalo cuối cùng đã được chấp nhận

```text
LỊCH HỌC GVNN — 24/10/2026

Thầy TEACHER A
17:30–18:00: HỌC SINH A - ALEX
21:00–21:30: HỌC SINH B - JOHNSON
LINK HỌC: https://example.com/meeting-a

Cô TEACHER B
18:30–19:00: HỌC SINH C - ANNA
LINK HỌC: https://example.com/meeting-b
```

- Gom toàn bộ tiết của một giáo viên vào cùng đoạn, giữ đủ từng tiết/học viên.
  Các đoạn theo giờ tiết đầu tiên; trong đoạn theo giờ tăng dần.
- Mỗi tiết **một dòng**, không thêm nhãn HỌC VIÊN, không có dòng trống giữa các tiết.
  Chỉ cách một dòng trống giữa các giáo viên. Link nằm cuối ngay đoạn của giáo viên đó.
- Cỡ chữ mặc định của Zalo; không dùng `f_18`, không dùng nhiều màu đỏ/cam.
  Tiêu đề và tên giáo viên đậm màu xanh lá; khung giờ và nhãn LINK HỌC in đậm.
  Danh xưng giữ dạng **Thầy/Cô**, tên giáo viên/học viên viết hoa. URL giữ nguyên hoàn toàn.
- Không gửi dòng Lớp, số buổi, học phí, lương hoặc thông tin phụ huynh.
- `edu.teacher.teaching_title` và `meeting_url` cấu hình trên form/list Giáo viên.
  Chưa chọn danh xưng thì dùng GV; thiếu link hiện CHƯA CẤU HÌNH LINK HỌC.
  Link phải là URL HTTP/HTTPS đầy đủ; cho phép query/password trong link Zoom.

## Luồng gửi và lỗi đã sửa

- `custom-addons/edu_zalo/models/zalo.py`: tạo nội dung, xếp hàng, gọi bridge và lịch sử gửi.
- `services/zalo-bridge/src/schedule-format.mjs`: các vùng định dạng native Zalo,
  dùng chỉ số UTF-16 của JavaScript, có kiểm tra tiếng Việt/emoji; không dùng HTML/Markdown.
- **Thủ công:** mỗi lần bấm sau khi gửi thành công tạo yêu cầu mới, lấy nội dung hiện tại.
  Đây là yêu cầu quan trọng: phiên trước từng chặn gửi lại cùng ngày, khiến người dùng
  thấy kết nối bình thường nhưng bấm gửi không có tin mới. Đã sửa, không khôi phục cách chặn đó.
- **Tự động:** tối đa một lịch mỗi ngày/nhóm, trong khoảng 12:00–12:30 giờ Việt Nam.
  Nếu máy chủ tắt suốt khoảng đó, không tự gửi bù; ngày không có tiết thì bỏ qua.
- Log có `send_mode` manual/daily, `request_key`, trạng thái, mã tin Zalo và thời điểm gửi.
  `init()` bỏ constraint cũ unique(date,group), thay bằng partial unique index riêng cho daily.
  Mã yêu cầu unique; bridge giữ sổ gửi để retry cùng yêu cầu không sinh tin lặp.
- Khi timeout/gián đoạn mà chưa rõ kết quả: trạng thái uncertain, không tự gửi lại.
  Cần kiểm tra thực tế trong nhóm trước khi xử lý. Không xóa ledger/lịch sử để né chống trùng.
- Lỗi kết nối: retry giữ nguyên mã/nội dung. Một lần gửi mới sau thành công lấy lại lịch mới nhất.
- Tin dài chia tối đa 1800 ký tự/phần, tối đa 20 phần. Đoạn giáo viên rất dài có thể qua nhiều phần;
  nếu cải tiến cách chia cần giữ đủ các tiết và link, thêm test tương ứng.

## Chạy và cấu hình

```powershell
docker compose up -d
docker compose --profile zalo up -d --build zalo-bridge
docker compose logs --tail 80 web zalo-bridge
```

- Bridge dùng Node 22, `zca-js` khóa ở **2.1.2**, có `package-lock.json`; không dùng Telegram.
- `.env.zalo` chứa khóa riêng, có mẫu `.env.zalo.example`; không in/commit khóa.
  Odoo dùng system parameters `edu_zalo.bridge_url` và `edu_zalo.bridge_token`.
- Bridge chỉ mở cổng 3000 trong Docker network, xác thực Bearer token.
  Volume `vn-hrm_zalo-bridge-data` giữ credentials, target và ledger; cần backup cùng DB.
- Đây là API Zalo cá nhân không chính thức; phiên có thể hết hạn và cần quét QR lại.
  Dịch vụ không mirror/đọc hội thoại. Chi tiết QR, chọn nhóm và vận hành ở [ZALO_SCHEDULE.md](ZALO_SCHEDULE.md).
- Đường dẫn local: `/web?db=gvnn#action=266` hoặc Trung tâm GVNN → Vận hành → Lịch học Zalo.
  ID action có thể khác trên máy khác.
- Khi đổi source bridge cần build lại; khi sửa model/view cần upgrade đúng module và restart web.
  Không chạy hai tiến trình Odoo cùng upgrade DB đang phục vụ; dừng web, chạy one-off rồi mở lại.
- Chỉ cài `edu_zalo` trên DB nghiệp vụ được chọn nếu dùng chung một bridge.
  Auto deploy Windows hiện có không tự provision bridge hoặc tự cài module mới.

## Dữ liệu import thử

- File local `Điểm Danh_GVNN .xlsx`, sheet Weekly, khác mẫu tổng hợp của wizard import cũ.
- Đã lưu trong `gvnn`: tuần 100 **52** buổi, tuần 101 **51**, tuần 102 **52**; tổng **155**.
  Có 74 học viên, 6 giáo viên, 5 lượt vắng, 70 video; đã kiểm tra giờ với Excel và chống nhập trùng.
- 18 dòng thiếu giờ được giữ 0 có ghi chú; không nhập học phí, số dư đầu kỳ hoặc đơn giá GV.
  Không dùng số liệu tài chính/lương của dữ liệu thử để kết luận đã đối soát.
- Excel chưa xác nhận hoàn thành; trạng thái Đã dạy dùng mặc định của model, có ghi chú nguồn.
- Mã import bắt đầu `weekly-v1-`. Import thử dùng script cục bộ trong `artifacts/weekly_trial/`,
  không phải tính năng mới của wizard `edu.import.wizard` và không nằm trong source được push.
  Không chạy lại script kiểm tra cũ có reset sequence trên DB thật.
- Excel, dữ liệu DB, filestore và log thử nghiệm không có trong Git. Máy khác cần restore/import riêng.
  Backup phiên này nằm ngoài repo ở `D:\Projects\vn-hrm-backups\`.

## Đăng nhập và kiểm tra

- Đã sửa hai controller login trong `vnpt_base` và `muk_theme/web_login_styles`:
  dùng auth public cho website; khi sai mật khẩu khôi phục env user thay vì ghi đè hàm update_env.
  Trang login đã trả 200 và nhập sai mật khẩu vẫn hiện form bình thường.
- Bridge có 10 test xác thực, đúng nhóm, format, offset UTF-16, chống trùng, timeout và restart.
- Odoo có 13 test về preview, nhóm giáo viên, link, URL, ngày Việt Nam, gửi trực tiếp,
  gửi lại thủ công, daily idempotency, quyền truy cập và lỗi/uncertain.
- Các test mock Zalo, không gửi tin thật. Có kiểm tra gửi thật vào nhóm thử và nhận mã tin từ Zalo.
  Các DB test tạo trong phiên đều được xóa sau khi kiểm tra.

```powershell
docker run --rm -v "${PWD}/services/zalo-bridge:/app:ro" -w /app node:22-alpine npm test
# Chạy trên DB thử/clone, không đặt test-enable lên service production:
docker compose run --rm --no-deps -T web odoo -d <test_db> -u edu_zalo --test-enable --test-tags /edu_zalo --stop-after-init --no-http --max-cron-threads=0
```

Việc tiếp theo chỉ làm theo yêu cầu mới của người dùng: chọn nhóm vận hành thật, bật gửi tự động,
hoặc cải tiến nghiệp vụ/lịch. Hiện chưa có yêu cầu bật gửi tự động lên nhóm thử.
