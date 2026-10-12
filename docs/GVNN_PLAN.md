# Kế hoạch: chuyển file `TỔNG HỢP_GVNN.xlsx` lên Odoo

Tài liệu bàn giao giữa các phiên làm việc. Đọc hết trước khi code tiếp, và cập nhật mục **Tiến độ** sau mỗi bước.

Nguồn: `TỔNG HỢP_GVNN.xlsx` ở thư mục gốc repo. Đây là sổ quản lý lớp luyện nói online 1 kèm 2 với giáo viên nước ngoài (GVNN), gồm điểm danh, học phí trả trước, lương GV theo giờ và các báo cáo.

## 0. Bắt đầu từ đây

**Bước tiếp theo:** các giai đoạn 1-8 đã xong. Còn lại chỉ là việc của người dùng và một câu hỏi:
1. Người dùng import dữ liệu thật vào DB `gvnn` (Cấu hình > Import Excel), đối chiếu theo bảng ở mục 5, rồi chạy "Cảnh báo tuần" và chốt các kỳ lương sau khi đối soát.
2. Quyết định về lương `STEPHAN` tháng 8-9 (xem mục 5) và rà soát ~298 buổi "Giờ dạy = 0".
3. Quyết định về các DB cũ `test`, `edu`, `edu2`, `edu3` và đặt `dbfilter = ^gvnn$` trong `config/odoo.conf` để tránh lỗi 403 của `gvnn` khi DB khác được nạp trước (xem *Lỗi đã biết* trong `CLAUDE.md`).
- Đã gỡ `vnpt_hrm_attendance` khỏi DB `gvnn` ngày 2026-10-09: module rỗng, `auto_install: True` nên được cài kèm, không module nào phụ thuộc. Sau lần `-u` kế tiếp nó vẫn ở trạng thái chưa cài. Nếu tạo DB mới và nó tự cài lại, gỡ bằng `button_immediate_uninstall()`.
- **DB `gvnn` hiện chưa có dữ liệu import.** Mọi lần thử đều rollback. Người dùng tự import qua menu Cấu hình > Import Excel (cần restart web để nhận code, đã làm ngày 2026-10-09), sau đó đối chiếu theo bảng ở mục 5.
- Tên hiển thị đã đổi từ "VNPT HRM" sang "KIM ACADEMY" trong source (`vnpt_base`: tiêu đề tab, mô tả module, tên hệ thống ở trang đăng nhập; `web_login_styles`). Tên module kỹ thuật (`vnpt_base`, `vnpt_hrm_dashboard`) và mã định danh XML giữ nguyên. DB đang chạy có thể vẫn còn giá trị cũ trong `ir_config_parameter` (`web.base.title`); DB tạo mới sẽ lấy giá trị mặc định mới.
- `edu.class.session_count` vẫn chưa làm.

**Quy tắc làm việc:**
- Làm xong mỗi giai đoạn thì đánh dấu `[x]` ở mục 6 và ghi một dòng vào nhật ký bên dưới.
- Mỗi giai đoạn phải cài được module trên DB `gvnn` và không có lỗi trong log trước khi chuyển sang giai đoạn sau.
- Khi nghiệp vụ thay đổi, sửa ngay mục 1 và mục 3, không chỉ ghi vào nhật ký.

**Nhật ký:**
- 2026-10-08: phân tích xong file Excel, chốt nghiệp vụ với người dùng. Chưa có code.
- 2026-10-08: kiểm tra kỹ thuật xong, làm xong **Giai đoạn 1**. Nhánh git `feature/edu-gvnn`. DB `gvnn` đã tạo, đã cài `edu_gvnn`, `vnpt_base`, `muk_theme/*`, `edu_landing`, không lỗi. Kiểm tra bằng Odoo shell: chuẩn hoá tên, đơn giá theo ngày hiệu lực, tuần tự tạo và chống trùng, quyền Giáo vụ không xem được đơn giá.
- 2026-10-08: làm xong **Giai đoạn 2** (buổi học, điểm danh, tính lương, cảnh báo buổi, chặn sửa đơn giá đã dùng). Test bằng Odoo shell: 31/31 kiểm tra đạt (lương, trừ học phí theo mặt/vắng, nghỉ buổi, testing, trùng buổi, đơn giá đổi, quyền Giáo vụ).
- 2026-10-09: làm xong **Giai đoạn 3** (phiếu thu/chi, số buổi tuỳ chọn, giảm giá, hoàn tiền, in phiếu, số dư và cảnh báo học phí). Test bằng Odoo shell: 28/28 đạt (mặc định 20 buổi = 2.000.000 đ, đổi buổi ↔ tiền, giảm giá, hoàn tiền, trừ học phí theo mặt/vắng, ngưỡng out/low, số dư đầu kỳ bỏ phiếu cũ, Giáo vụ không được hoàn tiền, render PDF phiếu thu/chi). Đổi nhãn `edu.student.attendee_ids` thành "Lượt tham dự" để hết cảnh báo trùng nhãn. Đã đặt lại sequence phiếu thu/chi về 1 sau test.
- 2026-10-09: commit GĐ1-3 (`c5af31b`, kèm code nháp GĐ4-6). Làm xong **Giai đoạn 4** (kỳ lương). Test bằng Odoo shell: 51/51 đạt (tính lương theo GV, buổi huỷ/vắng không tính, đối soát Agency lệch/khớp, chốt/khoá, chặn tạo-sửa-xoá buổi và HV trong tháng đã chốt, chặn chuyển buổi vào tháng đã chốt, chặn thêm/sửa/xoá đơn giá có hiệu lực trong tháng đã chốt, chỉ Admin mở khoá, ghi chatter, kỳ trùng tháng, render PDF đối soát Agency và lương GV trực tiếp). Đã thêm `period_id`/`locked` (tính, không lưu) vào `edu.session`.
- 2026-10-09: commit GĐ4 (`523b60f`). Làm xong **Giai đoạn 5** (cảnh báo tuần, chi phí khác, báo cáo tài chính, export tuần). Code đã có sẵn từ trước, chỉ thêm nút "Xuất điểm danh tuần" trên danh sách buổi học (`display="always"`) và đổi thứ tự nạp `alert_report_views.xml` lên trước `session_views.xml` trong manifest. Test bằng Odoo shell: 47/47 đạt (ưu tiên đỏ/vàng/ổn, nghỉ 3 tuần, đề xuất ngưng ≥ 4 tuần, buổi huỷ/vắng/testing không tính giờ, chạy lại không trùng và giữ ghi chú liên hệ, nút Ngưng học, SQL view tài chính khớp tổng thu/lương/chi phí khác/doanh thu, Giáo vụ không xem được báo cáo tài chính, xlsx 1 sheet `2.ĐIỂM DANH` đúng cột và dữ liệu). Chạy lại t3/t4/t5: 28 + 51 + 47 đều đạt.
- 2026-10-09: làm xong **Giai đoạn 6** (wizard import). Chạy thử trên file Excel thật (rollback, DB không đổi), khoảng 16 giây cho cả file. Sửa 1 lỗi: 20 dòng điểm danh có ngày lưu dạng chữ (`28/7/2026`) bị bỏ sót, nay đọc được và ghi vào log. Kiểm tra: chạy lại lần 2 không tạo thêm bản ghi nào; import theo khoảng 01/06-31/08 rồi chạy tiếp đến hết file không tạo trùng (886 buổi, 63 phiếu) và cho tổng số dư 60.918.333, đúng bằng Excel. Con số này khác 61.118.333 của lần import từ 01/01 vì buổi hủy 01/03/2026 nằm trước mốc 01/06 nên được gộp vào số dư đầu kỳ theo cách của Excel; chỉ import danh mục và học viên thì không tạo buổi hay phiếu; file sai trả về lỗi dễ hiểu; Giáo vụ không dùng được wizard. Đối chiếu mục 5: mọi chênh lệch đều có nguyên nhân (bảng trong mục 5), trừ 9,5 giờ GV.
- 2026-10-09: làm xong **Giai đoạn 7** (dashboard GVNN), tiếp tục từ bản viết dở có sẵn trong working tree (backend `edu.dashboard`, OWL, SCSS). `vnpt_hrm_dashboard` nay chỉ phụ thuộc `edu_gvnn`, đã xoá `hr_employee.py`. Bổ sung biểu đồ thu chi theo năm và biểu đồ loại cảnh báo. Kiểm tra bằng Chrome headless trên DB tạm `gvnn_ui` (đã xoá) có dữ liệu import thật: 5 thẻ KPI, 7 bộ đếm cảnh báo, bảng 8 học viên ưu tiên, 3 biểu đồ, không lỗi console, không cuộn ngang, click cảnh báo mở đúng danh sách; Giáo vụ không thấy số liệu tài chính. Đã chạy lại t3/t4/t5 (28 + 51 + 47) và `-u` không lỗi.
- 2026-10-09: làm xong **Giai đoạn 8**. DB `gvnn` có 41 module cài (`edu_gvnn`, `vnpt_hrm_dashboard`, `muk_web_*`, `edu_landing`, `vnpt_base` cùng phụ thuộc), `-u edu_gvnn,vnpt_hrm_dashboard` không lỗi, bundle `web.assets_frontend` và `web.assets_backend` không có `css_error_message`, landing page và 5 menu neo vẫn nguyên, user mới có trang chủ mặc định là dashboard. `hr`, `vnpt_hrm` chưa từng được cài. Gỡ `vnpt_hrm_attendance` (rỗng) khỏi `gvnn`. Cập nhật `CLAUDE.md` cho đúng dự án GVNN. Test t3/t4/t5 (28 + 51 + 47) đạt trên trạng thái cuối; DB không còn dữ liệu hay user thử.

**Phát hiện kỹ thuật (cần nhớ):**
- Nhật ký nhắc tới "t3/t4/t5/t6": đó là các script kiểm tra, nay nằm ở `scripts/gvnn_checks/` (`check_phase3_tuition.py` = t3, `check_phase4_payroll.py` = t4, `check_phase5_alerts_reports.py` = t5, `check_phase6_import.py` = t6). Cách chạy xem README trong thư mục đó. Chuyển sang máy mới: xem mục *Dựng trên máy mới* trong `CLAUDE.md`.
- `edu.week.alert` là ảnh chụp lúc tạo nên có thể cũ so với học viên (nhiều học viên lệch số dư/cảnh báo học phí sau khi import). Dashboard gọi `_generate(week)` mỗi lần mở để số liệu khớp. Danh sách cảnh báo mở từ menu vẫn là bản đã tạo, cần chạy lại "Cảnh báo tuần" để cập nhật.
- Trong SCSS, `.vd-card` đặt `grid-column: span 12` nên phần tử con có thêm class `vd-card` trong lưới riêng phải đặt lại `grid-column: auto`. Kiểm tra layout bằng Chrome headless (xem mục Kiểm tra giao diện trong `CLAUDE.md`), đừng tin thông số trong DB không có dữ liệu vì các thẻ biểu đồ và bảng khi đó chưa hiện.
- Màu chữ `h1` của theme đè lên màu của khối nền xanh, phải đặt `color: inherit`. Tương phản đo được: 4,53 đến 15,43 (đạt AA).
- File gốc có ô ngày lưu dạng chữ (`28/7/2026`) và tên GV thừa dấu cách (`STEPHAN `). Excel xử lý hai trường hợp này sai (bỏ dòng, báo thiếu đơn giá); importer xử lý đúng nên tổng lệch so với Excel.
- Máy host (Python 3.9) có `openpyxl` 3.1.5, đọc được công thức của file Excel khi cần; container thì không. Khi in tiếng Việt ra console Windows phải đặt `PYTHONIOENCODING=utf-8`.
- `edu.student.name` bị viết hoa toàn bộ (`T5 A - AMY`); xlsx export và khớp tên khi import đều dùng dạng này.
- `message_post` báo "Unable to send message, please configure the sender's email address" khi người dùng không có email (ví dụ admin mặc định). Dùng `sudo().message_post(..., author_id=env.user.partner_id.id)`, xem `EduPayrollPeriod._log`.
- Field tính không lưu phụ thuộc bản ghi khác (như `edu.session.period_id`) không tự xoá cache khi kỳ lương đổi trong cùng giao dịch. Gọi `invalidate_model([...])`, xem `_invalidate_sessions`.
- Khi render PDF trong shell, log có cảnh báo `wkhtmltopdf ... ContentNotFoundError`. Vô hại, PDF vẫn được tạo (đã kiểm tra bằng `%PDF`).
- Trên Odoo 17, field tính toán có `store=True` mà có `default=` thì **không được tính lại khi create** (giá trị mặc định được coi như đã cung cấp). `edu.session.minutes` vì thế không có `default`, mặc định 30 phút nằm trong hàm tính.
- Khi chạy script test bằng `odoo shell`, copy file vào container rồi chạy `odoo shell -d gvnn --no-http < /tmp/x.py > /tmp/x.out`. Pipe trực tiếp từ PowerShell có thể treo.
- Container Odoo **không có `openpyxl`**. Có `xlrd 1.2.0` (đọc được xlsx, giá trị cache của công thức; mở file mất khoảng 11 giây), `xlsxwriter 3.0.2`, `num2words`. **Wizard import dùng `xlrd`**, ngày đọc ở dạng số serial nên phải đổi bằng `xlrd.xldate_as_datetime`. Không cần đổi image Docker.
- Odoo 17 dùng thẻ `<app>`, `<block>`, `<setting>` cho màn hình Thiết lập; không dùng `div.settings`, `app_settings_block` như bản cũ.
- Khi test bằng Odoo shell, `ir.sequence` kiểu standard không hoàn lại khi rollback. Phải đặt lại `number_next_actual = 1` cho các sequence `edu.student`, `edu.tuition.payment`, `edu.tuition.refund` sau khi test.
- Trên Git Bash, copy script vào container bằng `MSYS_NO_PATHCONV=1 docker compose cp "$(cygpath -m /tmp/x.py)" web:/tmp/x.py`. Đường dẫn `/tmp/...` thô của Git Bash không dùng được với `docker compose cp`. Chạy shell bằng `docker compose exec -T web sh -c "odoo shell -d gvnn --no-http < /tmp/x.py > /tmp/x.out 2>&1"` rồi `grep` file `.out`.
- `vnpt_hrm_dashboard` hiện vẫn phụ thuộc `vnpt_hrm` (kéo theo HR), **chưa cài trên DB `gvnn`**. Sẽ viết lại ở Giai đoạn 7.
- Docker Desktop trên máy có thể chưa chạy: mở ứng dụng rồi `docker compose up -d`. Chạy lệnh trong Odoo: `docker compose exec -T web odoo -d gvnn -u edu_gvnn --stop-after-init --no-http`.

## 1. Quyết định đã chốt với người dùng

1. **Giáo viên** dùng model riêng `edu.teacher`, không dùng `hr.employee`. Có 2 loại GV:
   - **Qua Agency:** hiện chỉ có 1 Agency, nhưng vẫn lưu `agency_id` để mở rộng sau này.
   - **Làm trực tiếp** với trung tâm.
2. **Học phí:** mặc định 100.000 đ cho mỗi block 30 phút, áp dụng cho mọi học viên. Có thể sửa đơn giá block **riêng cho từng học viên trong từng buổi** (ví dụ 150.000 đ), block vẫn là 30 phút.
3. **Học viên vắng** thì không bị trừ học phí. **GV không được tính lương** nếu buổi không có học viên nào có mặt.
4. **Loại buổi** (`session_type`) có 2 giá trị:
   - `lesson`: buổi học thường, có **1 hoặc 2 HV** (ràng buộc tối đa 2). GV được tính lương nếu ít nhất 1 HV có mặt.
   - `testing`: buổi test hoặc demo. Chỉ cần biết **test lớp nào** (`class_ids`), **không nhập HV** (ẩn tab HV). HV tham dự là HV cũ thuộc lớp đó, xem qua danh sách HV của lớp. Không trừ học phí ai. GV được tính lương.
   - Mỗi HV trong buổi `lesson` có **nút "Đánh nghỉ"** (bật/tắt `present`) để người dùng tự đánh dấu HV vắng. HV vắng thì không bị trừ tiền.
   - **Trạng thái buổi:** khi giáo vụ nhập thì mặc định là `done` (đã dạy), không có bước xác nhận.
     - Nút **"Nghỉ buổi học"** chuyển sang `cancel`: không trừ tiền HV và không tính lương GV.
     - Nút **"Khôi phục"** chuyển về `done`.
     - Không có trạng thái nháp, nên chỉ số "buổi chưa hoàn tất" của Excel được thay bằng **"buổi có cảnh báo"** trong tuần.
5. **Lương GV trả theo tháng** và quản lý bằng **kỳ lương** `edu.payroll.period`.
   - Người quản lý bấm **Chốt lương**. Sau khi chốt thì khoá: không tạo, sửa, xoá buổi học hoặc HV trong buổi của tháng đó, và không sửa đơn giá có hiệu lực trong tháng đó.
   - Chỉ **Admin** có nút **Mở khoá**.
   - Phải **in được bảng đối soát (PDF) gửi Agency**.
6. **Thu học phí:**
   - HV đóng tiền mỗi lần hết buổi. **Phụ huynh chọn số buổi muốn học**, không cố định theo gói.
     - Phiếu thu nhập **số buổi** (mỗi buổi = 1 block 30 phút). Tiền = số buổi × đơn giá block, sửa được.
     - **Mặc định khi tạo phiếu: 20 buổi = 2.000.000 đ** (cấu hình `default_blocks` = 20 × `block_price` = 100.000 đ).
     - Người dùng có thể đổi số buổi, hoặc nhập trực tiếp số tiền (khi đó số buổi tính ngược lại = tiền ÷ đơn giá block).
   - Có **giảm giá** và **hoàn tiền**.
   - Phải **in phiếu thu** (in phiếu chi khi hoàn tiền).
7. **Ngưng học:** vừa có nút chuyển tay (Ngưng học / Học lại), vừa được hệ thống **gợi ý** trong cảnh báo tuần khi HV nghỉ ≥ N tuần (cấu hình `stop_suggest_weeks`, mặc định 4).
8. **Lớp** là một danh mục riêng `edu.class`: tên, nhóm Zalo, danh sách HV, GV phụ trách, ghi chú.
9. **Người dùng** hiện chỉ có 3 vai: Giáo vụ, Quản lý, Admin. Không có nhóm Kế toán.
10. **Chi phí khác:** tạo sẵn danh mục `edu.expense.category`: Phần mềm/Zoom, Marketing, Lương giáo vụ, Mặt bằng/điện nước, Học liệu, Khác.
11. **Export Excel theo tuần:** chọn tuần và xuất ra file xlsx chỉ gồm 1 sheet `2.ĐIỂM DANH`, giữ đúng cột và tiêu đề như file gốc (dùng `xlsxwriter`).
12. Giờ trong điểm danh là **giờ Việt Nam**. Lưu dạng float (widget `float_time`) để tránh lệch múi giờ.
13. **Số tuần giữ cách đánh số riêng** của file: tuần 1 bắt đầu 10/10/2024, đến 21/09/2026 là tuần 98. Số tuần **không tuyến tính** (có tuần nghỉ, ví dụ Tết), nên phải có bảng tuần `edu.week`, không tính bằng công thức.
14. **Import dữ liệu cũ dần dần, ưu tiên từ 01/01/2026.** Phần trước ngày bắt đầu import được gộp thành **số dư đầu kỳ** của từng học viên.
15. Chạy trên **database mới tên `gvnn`**, cài được `edu_landing`.
16. Chỉ giữ và tái dùng `vnpt_base`, `muk_theme/*`, `edu_landing` và `vnpt_hrm_dashboard`. Dashboard sẽ viết lại thành dashboard GVNN và bỏ phụ thuộc HR.
   - Các phần còn lại là thừa của hệ thống cũ, không được phụ thuộc vào chúng: `vnpt_hrm`, `vnpt_hrm_attendance`, `vnpt_hrm_payroll`, `required-addons/hr_payroll`.
   - Chưa xoá các module này. Phải hỏi người dùng trước khi xoá.

## 2. Nghiệp vụ trích từ file Excel

| Sheet | Nghiệp vụ |
|---|---|
| `DANH MỤC` | Danh sách GV và **lịch sử đơn giá theo giờ** (GV, ngày hiệu lực, đơn giá). Đơn giá áp dụng cho một ngày là dòng có ngày hiệu lực gần nhất ≤ ngày đó. Khi đổi giá thì thêm dòng mới, không sửa dòng cũ. |
| `2.ĐIỂM DANH` | Mỗi dòng là một buổi: STT, tuần, thứ, ngày, GV, HV1/HV2/HV3 (chuỗi "TÊN VIỆT - TÊN ANH"), lớp, giờ bắt đầu/kết thúc, phút, giờ tính HV (N), giờ tính GV (O), trạng thái hoàn thành (P, chữ tự do), ghi chú, recording, điểm. Khoảng 5.666 dòng. |
| `DL_LƯƠNG_THEO_NGÀY` (ẩn) | Lương buổi = giờ GV × đơn giá tại ngày dạy. Cảnh báo theo thứ tự: THIẾU GIÁO VIÊN → GIỜ DẠY = 0 → CHƯA CÓ ĐƠN GIÁ → GV CHƯA CÓ TRONG DANH MỤC → TRÙNG BUỔI (cùng ngày, GV, lớp, giờ bắt đầu; dòng sau bị đánh dấu) → OK. |
| `LƯƠNG GVNN CHI TIẾT` | Lương theo ngày và theo tuần (thứ Hai đến Chủ nhật). Trạng thái tuần: THỰC TẾ, ĐANG CẬP NHẬT, CHƯA PHÁT SINH. |
| `TH LƯƠNG GVNN` | Lương theo tháng và năm (kèm % so với năm trước). Bảng **GV × tháng** gồm số buổi, giờ, đơn giá cuối tháng, lương nội bộ, cùng **giờ và lương Agency nhập tay**. Tính độ lệch và trạng thái: KHÔNG CÓ BUỔI DẠY, CHƯA CÓ ĐƠN GIÁ, CÓ CẢNH BÁO, LỆCH AGENCY (lệch giờ > 0,01 hoặc lệch tiền > 1 đ), OK. |
| `4. THU HỌC PHÍ GVNN` | Mỗi HV có mã `HV###`, tên Việt, tên Anh, lớp, tình trạng (1 = còn học, 0 = ngưng), và tiền thu ghi thành **một cột mỗi tháng**. Đã thu = tổng các tháng. Số dư = đã thu − tiền đã học. Cảnh báo (chỉ HV còn học): số dư < 1 → HẾT HỌC PHÍ; số dư < 300.000 → Gần hết học phí. Công nợ dự kiến = số dư > 0 của HV còn học. |
| `3.THEO DÕI HỌC SINH` | Giờ đã học = tổng giờ HV của các buổi có HV đó. Buổi = giờ × 2. Tiền đã học = buổi × 100.000. Buổi đã đóng = đã thu ÷ 100.000. Còn lại ≤ 3 buổi → "Sắp hết buổi". Có cột nhóm Zalo. |
| `CẢNH BÁO TUẦN MỚI` | Nhập số tuần N. Với mỗi HV còn học tính: giờ tuần N, N-1, N-2; NGHỈ nếu tuần N = 0; NGHỈ 3 TUẦN LIÊN TIẾP; số buổi trong tuần; buổi gần nhất; cảnh báo học phí; số dư; buổi còn lại; buổi chưa hoàn tất. Ưu tiên và hành động xem bảng ngay dưới. |
| `BÁO CÁO TỔNG HỢP` | Theo tháng/năm: tiền thu, số HS đóng, thu bình quân/HS, số buổi, giờ, lương GV, **chi phí khác (nhập tay)**, tổng chi, dòng tiền sau chi, tỷ lệ chi/thu, số cảnh báo lương. Thêm các KPI năm hiện tại. |
| `BÁO CÁO CHUNG` | Tổng HV đăng ký, đang học, đã ngưng. Thu theo tháng. Chi lương theo tháng và bình quân/giờ. Lợi nhuận gộp = doanh thu ghi nhận (tiền đã học) − lương GV. Công nợ thu trước. |
| `DASHBOARD` | 5 thẻ KPI (HS đang học, thu năm nay, chi năm nay, dòng tiền, số dư học phí), các bộ đếm cảnh báo, biểu đồ tháng/năm/loại cảnh báo, gợi ý quản trị. |

Ưu tiên và hành động đề xuất trong `CẢNH BÁO TUẦN MỚI`:

| Điều kiện | Ưu tiên | Hành động đề xuất |
|---|---|---|
| Nghỉ 3 tuần liên tiếp | ĐỎ - LIÊN HỆ NGAY | Gọi phụ huynh, xác nhận lịch học và học phí |
| Hết học phí | ĐỎ | Liên hệ trong ngày |
| Nghỉ tuần này hoặc gần hết học phí | VÀNG | Theo dõi và nhắc trong tuần |
| Còn lại | ỔN | Không cần xử lý |

Lưu ý: "Tiền thu" là dòng tiền thu học phí, **không phải doanh thu kế toán**. Doanh thu ghi nhận là tiền đã học.

### Lỗi dữ liệu trong Excel cần xử lý khi import

- **Tên GV không chuẩn:**
  - `STEPHAN ` thừa dấu cách: bỏ khoảng trắng.
  - `LURICH` là cách viết khác của `LUIRICH`: gộp làm một.
  - `STEFAN` và `STEPHAN` là **2 GV khác nhau**, đơn giá khác nhau.
  - `ANTHONY`, `SUNE` không có trong danh mục: tạo GV mới, chưa có đơn giá.
- **Học viên được khớp bằng chuỗi "VIỆT - ANH"** (viết hoa, gộp khoảng trắng). Tên không khớp HV nào đưa vào trường "người tham gia khác" của buổi, không tạo HV.
- **Nhận diện buổi `testing`:** ô học viên chứa `TESTING` (ví dụ `TESTING GRADE 3.4`), hoặc cột trạng thái/ghi chú chứa `DEMO` hay `TEST`. Các buổi còn lại là `lesson`.
  - Với `TESTING <lớp>`, phần sau chữ TESTING là lớp được test, đưa vào `class_ids`.
  - Buổi testing không tạo attendee.
- **Cột P "done (only Bob)"** nghĩa là chỉ HV có tên Anh là Bob có mặt, các HV còn lại vắng.
- Có chữ `CANCEL` (ở cột P hoặc các cột ghi chú) thì buổi là **đã hủy**.
- Các cột Q..X bị lệch so với tiêu đề do lỗi `#REF!` từ file nguồn. Xử lý:
  - Q, R, S: gộp vào ghi chú.
  - Giá trị bắt đầu bằng `http`: đưa vào link recording.
  - Điểm W, X: chỉ lấy khi là số > 1.
- Cột "Số buổi còn lại dự kiến" trong sheet cảnh báo bị sai công thức. Hệ thống mới tính đúng: số dư ÷ đơn giá block.
- Lớp ghép dạng `GRADE 3.1 + GRADE 4.2`: tách theo dấu `+`. Giá trị `GVNN` cũng tạo thành một lớp.

## 3. Thiết kế module mới `custom-addons/edu_gvnn`

**Phụ thuộc:** `base`, `mail`, `web`, `vnpt_base`. Không dùng `account` hay `hr`.

### Model

| Model | Trường và quy tắc chính |
|---|---|
| `edu.teacher` (mail.thread) | name (viết hoa, duy nhất), code, **teacher_type (agency/direct)**, agency_id (res.partner, bắt buộc nếu là agency), phone, email, active, rate_ids, `current_rate` (tính tự động), `_get_rate(date)` |
| `edu.teacher.rate` | teacher_id, date_from, rate (đ/giờ). Ràng buộc duy nhất (teacher, date_from). **Đã làm:** sửa/xoá bị chặn nếu GV có buổi **đã trả lương** (`paid`) từ date_from trở đi, khi đó phải thêm dòng mới. Thêm/sửa/xoá đơn giá thì tính lại đơn giá của các buổi **chưa trả lương** từ date_from. Giai đoạn 4 sẽ thêm điều kiện "tháng đã chốt lương". |
| `edu.class` | name (duy nhất), zalo_group, student_ids (many2many hai chiều với `edu.student.class_ids`), teacher_ids, active, note, student_count, session_count |
| `edu.expense.category` | name. Có dữ liệu tạo sẵn (xem mục 1, quyết định 10). |
| `edu.week` | number (duy nhất), date_from, date_to, không chồng lấn. `_get_week(date)`: nếu ngày vượt tuần cuối thì tự tạo tuần kế tiếp (thứ Hai đến Chủ nhật, số = số cuối + 1). |
| `edu.student` (mail.thread) | code (sequence `HV###`), name_vi, name_en, `name` = "VI - EN" (lưu lại, dùng để khớp khi import), class_ids, zalo_group, parent_name, phone, state (studying/stopped) với nút **Ngưng học / Học lại**, **opening_date, opening_balance**. Các trường tính và lưu: total_paid, learned_hours, learned_blocks, learned_amount, balance, remaining_blocks, fee_warning (out/low), last_session_date. |
| `edu.session` | date, week_id (tính từ date, cho sửa), weekday, **session_type (lesson/testing, mặc định lesson)**, teacher_id, class_ids, time_start/time_end (float), minutes, student_hours, teacher_hours (mặc định = phút/60, cho sửa), state (**done mặc định / cancel**, nút "Nghỉ buổi học" và "Khôi phục"), period_id/locked (tính từ kỳ lương của tháng), completion_note, attendee_ids, extra_participants, note, recording_url, video_posted, paid (đã trả lương GV), teacher_rate (lưu lại), paid_hours, teacher_amount, warning (selection), import_key (duy nhất) |
| `edu.session.attendee` | session_id, student_id, present (mặc định True), score, block_price (mặc định từ cấu hình), charge_hours, blocks, charge_amount. Các trường date, week_id, teacher_id là related có lưu. Ràng buộc duy nhất (session, student). Trong danh sách HV của form buổi học, mỗi dòng có nút **Đánh nghỉ / Có mặt** (`action_toggle_present`); dòng vắng hiển thị mờ hoặc gạch ngang. |
| `edu.tuition.payment` | ref (sequence PT/PC), student_id, date, **payment_type (payment/refund)**, **blocks** (số buổi phụ huynh chọn, mặc định `default_blocks`), **block_price** (mặc định từ cấu hình, sửa được), **gross_amount** (= blocks × block_price, có thể nhập tay), **discount_amount**, **amount** (tiền thực thu = gross − giảm giá; hoàn tiền thì âm), method (cash/transfer/other), payer_name, note, user_id, import_key (duy nhất). Báo cáo **in phiếu thu / phiếu chi** (QWeb PDF, có số tiền bằng chữ qua `currency.amount_to_text`). |
| `edu.payroll.period` (mail.thread) | name ("Lương MM/YYYY"), date_from (ngày 1), date_to (cuối tháng), state (open/locked), line_ids, locked_by, locked_date. Tháng duy nhất. Nút: **Tính lương** (tạo/cập nhật dòng cho mọi GV có buổi), **Chốt lương** (Quản lý: tính lại, lưu số liệu, đánh `paid` cho các buổi, khoá), **Mở khoá** (chỉ Admin, ghi log vào chatter). Báo cáo PDF: **Bảng đối soát Agency** (các GV agency, tổng hợp và chi tiết buổi), **Bảng lương GV trực tiếp**. |
| `edu.payroll.line` | period_id, teacher_id, teacher_type, agency_id, session_count, hours, amount, rate_end_month (lưu lại khi tính), agency_hours, agency_amount (nhập tay), diff_hours, diff_amount, status (no_session/no_rate/warning/agency_diff/ok). Thay cho `edu.agency.statement` trong bản trước. |
| `edu.other.expense` | date, name, category_id, amount |
| `edu.week.alert` | Dòng cảnh báo, lưu lại để giáo vụ theo dõi: week_id, student_id, giờ tuần N/N-1/N-2, absent, absent_3w, session_count, last_session_date, fee_warning, balance, remaining_blocks, warning_sessions, **suggest_stop** (nghỉ ≥ `stop_suggest_weeks` tuần), priority, action, contacted, contact_note. Có nút "Ngưng học" ngay trên dòng cảnh báo. Hàm `_generate(week)` xoá dòng cũ của tuần rồi tạo lại. |
| `edu.report.finance` | SQL view (`_auto=False`), UNION của thu học phí, lương GV, chi khác và doanh thu ghi nhận. Các cột: date, income, salary, other_expense, total_cost, cash_flow, revenue. Dùng cho pivot/graph theo tháng và năm. |
| `res.config.settings` | block_minutes (30), block_price (100000), default_blocks (20, mặc định số buổi trên phiếu thu), fee_out_threshold (1), fee_low_threshold (300000), absent_weeks (3), stop_suggest_weeks (4). Lưu bằng `ir.config_parameter`. |
| `edu.export.week.wizard` | Chọn tuần và xuất xlsx 1 sheet `2.ĐIỂM DANH` cùng cột với file gốc: STT, TUẦN, THỨ, NGÀY, THÁNG, GIÁO VIÊN, HỌC VIÊN 1-3, LỚP, GIỜ BẮT ĐẦU, GIỜ KẾT THÚC, PHÚT, GIỜ HV, GIỜ GV, STATE OF COMPLETION, NOTE, RECORDINGS, POSTED VIDEO, PAID, SCORE 1-2, THÁNG, NĂM. Buổi testing ghi `TESTING <lớp>` vào ô HV1. Buổi nghỉ ghi `CANCELED`; HV vắng ghi vào cột trạng thái, ví dụ `done (only Bob)`. Có nút trên list và menu. |

### Công thức

- **Trừ học phí:** buổi `lesson`, trạng thái `done`, và HV có mặt.
  - charge_hours = student_hours
  - blocks = charge_hours × 60 / block_minutes
  - charge_amount = blocks × block_price
- **Lương GV:** buổi `done` (buổi `cancel` thì không tính lương và không trừ tiền), và thoả một trong hai điều kiện:
  - `testing`: không cần thêm điều kiện.
  - `lesson`: có ít nhất một HV có mặt.
  - paid_hours = teacher_hours
  - teacher_amount = paid_hours × teacher_rate
- **Số dư HV** = opening_balance + Σ thu (ngày ≥ opening_date) − Σ charge_amount (ngày ≥ opening_date).
  - Dữ liệu trước opening_date được import sau này sẽ **không** làm sai số dư.
- **Cảnh báo buổi:** missing_teacher, zero_hours, no_rate, duplicate (đã có buổi id nhỏ hơn cùng ngày, GV và giờ bắt đầu), no_student (buổi `lesson` không có HV), ok. Buổi `lesson` có hơn 2 HV thì chặn lưu (constraint).
- **Báo cáo lương** tách được theo loại buổi. **Cảnh báo tuần** chỉ tính giờ học từ buổi `lesson`.

### Phân quyền

| Nhóm | Quyền |
|---|---|
| Giáo vụ (`group_edu_staff`) | Buổi học (tạo, sửa, nghỉ buổi), HV, lớp, thu học phí và in phiếu thu, cảnh báo tuần, export tuần, xem GV (không xem đơn giá hay lương) |
| Quản lý (`group_edu_manager`) | Kế thừa Giáo vụ. Thêm: GV và đơn giá, kỳ lương (tính, chốt, in đối soát), hoàn tiền, chi phí khác, báo cáo tài chính, cấu hình, import, xoá bản ghi |
| Admin (`base.group_system`) | Toàn quyền, có nút **Mở khoá kỳ lương**. User admin được gán thêm nhóm Quản lý. |

### Menu "Trung tâm GVNN"

- Vận hành: Buổi học, Cảnh báo tuần, Export điểm danh tuần
- Học viên: Học viên, Lớp, Thu học phí
- Giáo viên: Giáo viên, Kỳ lương (Quản lý)
- Báo cáo (Quản lý): Lương GV (pivot/graph trên `edu.session`), Tài chính, Học phí
- Cấu hình (Quản lý): Tuần, Chi phí khác, Danh mục chi phí, Thiết lập, Import Excel

### Wizard import `edu.import.wizard`

- **Đầu vào:** file xlsx (đọc bằng `xlrd`, lấy giá trị cache của công thức), date_from (mặc định 01/01/2026), date_to, các lựa chọn: danh mục GV/đơn giá/lớp/tuần, học viên, thu học phí, buổi học, đặt số dư đầu kỳ.
- **Tuần:** import mọi số tuần có trong sheet điểm danh, tính khoảng ngày của mỗi tuần từ ngày sớm nhất đến ngày muộn nhất.
- **Học viên:** lấy toàn bộ từ sheet 4, khớp theo mã ở cột AK. Trạng thái lấy từ cột AI, nhóm Zalo từ sheet 3 cột F.
- **Lớp:** tạo từ cột LỚP (tách theo dấu `+`) và từ các ô `TESTING <lớp>`. Gán HV vào lớp theo các buổi `lesson` HV đã học với lớp đó, bỏ qua lớp `GVNN`.
- **Kỳ lương:** sau khi import buổi học, tạo kỳ lương cho các tháng đã qua, ở trạng thái **open**. Người dùng tự chốt sau khi đối chiếu. Import không được ghi vào tháng đã khoá.
- **Phiếu thu import:** payment_type = payment, gross_amount = amount, blocks = amount ÷ block_price, discount = 0. Số âm (điều chỉnh) thì tạo thành refund.
- **Thu học phí:** mỗi ô tháng khác 0 tạo một phiếu, ghi ngày 1 của tháng, import_key = `<mã HV>-<YYYY-MM>`. Tháng trước date_from không tạo phiếu, chỉ cộng vào số dư đầu kỳ.
- **Số dư đầu kỳ** tại date_from = Σ tiền thu các tháng trước date_from − Σ (giờ HV × 2 × 100.000) của các buổi trước date_from. Cách tính này giống Excel.
- **Buổi học:** lấy các dòng có ngày trong khoảng, import_key = `xlsx-<STT>`. Dòng đã có thì bỏ qua, nên chạy lại nhiều lần không bị trùng.
- **Kết quả:** báo số bản ghi đã tạo, tên GV và HV không khớp.
- Container chỉ có `xlrd` 1.2.0, không có `openpyxl`. File `THỔNG HỢP_GVNN.xlsx` phải được người dùng upload qua wizard (không mount vào container).

## 4. Dashboard: viết lại `vnpt_hrm_dashboard`

- Đổi phụ thuộc từ `vnpt_hrm` sang `edu_gvnn`. Bỏ code về `hr.employee`.
- Giữ cấu trúc client action OWL (`owl.vnpt_hrm_dashboard`) và Chart.js qua `loadBundle("web.chartjs_lib")`.
- Nội dung:
  - Thẻ KPI: HS đang học, thu năm nay, tổng chi năm nay, dòng tiền sau chi, số dư học phí.
  - Bộ đếm cảnh báo tuần hiện tại: nghỉ trong tuần, nghỉ 3 tuần, hết học phí, gần hết học phí, ưu tiên đỏ, buổi có cảnh báo, đề xuất ngưng học.
  - Biểu đồ 12 tháng (thu, lương, dòng tiền), biểu đồ theo năm, biểu đồ loại cảnh báo.
  - Danh sách HV ưu tiên đỏ.
- Theo quy ước SCSS trong `CLAUDE.md`: dùng biến màu của Odoo, không hard-code.

## 5. Số liệu đối chiếu sau khi import (lấy từ Excel)

| Chỉ số | Giá trị Excel |
|---|---|
| HV đăng ký / còn học | 188 / 84 |
| Tổng tiền thu lũy kế | 1.069.478.333 |
| Tiền đã học lũy kế | 976.840.000 |
| Số dư học phí của HV còn học | 60.918.333 |
| Tổng công nợ dự kiến (số dư > 0, HV còn học) | 64.091.666 |
| Thu năm 2026 | 292.898.333 |
| Lương GV năm 2026 (tháng 1–9) | 130.939.708 |
| Lương 2025 | 248.715.000 |
| Lương 2024 | 28.570.000 |
| Thu 2025 | 657.480.000 |
| Thu 2024 | 119.100.000 |
| Giờ GV năm 2026 / số buổi 2026 | 1.069,075 / 2.227 |

Lương theo tháng năm 2026:

| Tháng | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| Lương (đ) | 20.942.750 | 9.108.625 | 18.577.500 | 16.049.583 | 19.080.000 | 10.925.833 | 13.997.500 | 14.311.667 | 7.946.250 |

Có thể lệch nhỏ vì hệ thống mới không tính buổi đã hủy và HV vắng (Excel vẫn tính). Khi lệch phải ghi rõ nguyên nhân.

### Kết quả đối chiếu thật (import file Excel ngày 2026-10-08, từ 01/01/2026, 2026-10-09)

| Chỉ số | Excel | Hệ thống | Nguyên nhân lệch |
|---|---|---|---|
| HV đăng ký / còn học | 188 / 84 | 188 / 84 | khớp |
| Thu năm 2026 | 292.898.333 | 292.898.333 | khớp |
| Số buổi 2026 | 2.227 | 2.247 | +20 dòng có ngày lưu dạng chữ `28/7/2026` (dòng 5199-5219), Excel bỏ sót, hệ thống đọc được |
| Số dư HV còn học | 60.918.333 | 61.118.333 | +200.000: buổi hủy dòng 3873 (01/03/2026, GV BELLA, HV Oliver và Andy), Excel vẫn trừ tiền |
| Công nợ dự kiến | 64.091.666 | 64.291.666 | cùng +200.000 ở trên |
| Lương T1, T2, T4, T5, T6 | | | khớp (lệch dưới 1 đ do làm tròn) |
| Lương T3 | 18.577.500 | 18.675.000 | +97.500 = +165.000 (GV `LURICH` gộp vào `LUIRICH`, Excel không có đơn giá) − 67.500 (buổi hủy của BELLA, Excel vẫn trả) |
| Lương T7 | 13.997.500 | 15.262.500 | +1.265.000 đúng bằng 20 dòng ngày dạng chữ ở trên |
| Lương T8 | 14.311.667 | 16.231.667 | +1.920.000: GV `STEPHAN ` (thừa dấu cách) bị Excel báo "chưa có đơn giá" nên trả 0, hệ thống bỏ dấu cách và dùng đơn giá 240.000 |
| Lương T9 | 7.946.250 | 8.786.250 | +840.000, cùng nguyên nhân STEPHAN |
| Lương 2026 | 130.939.708 | 135.062.208 | tổng +4.122.500 = 97.500 + 1.265.000 + 1.920.000 + 840.000 |
| Giờ GV 2026 | 1.069,075 | 1.078,575 | lệch 9,5 giờ, **chưa tách riêng nguyên nhân** |

**Việc người dùng cần quyết định:** Excel có đang trả lương cho STEPHAN tháng 8 và 9 không (2.760.000 đ)? Excel đang ghi 0 vì lỗi dấu cách. Nếu thực tế chưa trả thì xem lại trước khi chốt lương hai tháng này.

Dữ liệu cần biết: có 298 buổi trạng thái `done` mang cảnh báo "Giờ dạy = 0", ngày đến 26/09/2026. Phần lớn (khoảng 286) là dòng Excel để trống cột giờ HV và giờ GV, nên không trừ tiền HV và không tính lương. Khoảng 11 buổi có giờ HV nhưng giờ GV trống, nên HV bị trừ tiền còn GV không có lương. Giáo vụ nên rà soát cả hai nhóm.

## 6. Tiến độ

- [x] Phân tích file Excel và chốt các quyết định (mục 1, 2)
- [x] Kiểm tra kỹ thuật trước khi code (kết quả ở nhật ký, mục 0)
- [x] GĐ1: Khung module `edu_gvnn`: manifest, phân quyền (Giáo vụ/Quản lý/Admin), cấu hình, `edu.teacher` (loại agency/direct) và đơn giá, `edu.class`, `edu.week`, `edu.student` (Ngưng/Học lại), `edu.expense.category` và dữ liệu tạo sẵn
- [x] GĐ2: `edu.session` (lesson/testing, Nghỉ buổi học/Khôi phục) và attendee (nút Đánh nghỉ), tính lương, cảnh báo buổi. **Chưa làm:** `period_id`/khoá theo kỳ lương (GĐ4), `import_key` (GĐ6).
- [x] GĐ3: Thu học phí (số buổi tuỳ chọn, giảm giá, hoàn tiền), in phiếu thu/chi, số dư, cảnh báo học phí
- [x] GĐ4: Kỳ lương (tính, chốt, khoá, mở khoá cho Admin), in bảng đối soát Agency và bảng lương GV trực tiếp
- [x] GĐ5: Cảnh báo tuần (đề xuất ngưng học), chi phí khác, báo cáo tài chính (SQL view), export điểm danh tuần ra xlsx
- [x] GĐ6: Wizard import Excel, import từ 01/01/2026, đối chiếu với mục 5
- [x] GĐ7: Viết lại `vnpt_hrm_dashboard` thành dashboard GVNN
- [x] GĐ8: Tạo DB `gvnn`, cài `edu_gvnn`, `vnpt_hrm_dashboard`, `muk_theme/*`, `edu_landing`, `vnpt_base` và kiểm tra lỗi
  - `command: -u vnpt_base` trong `docker-compose.yml` giữ nguyên: nâng cấp `vnpt_base` mỗi lần khởi động chạy sạch (đã xem log), không ảnh hưởng `gvnn`.
- [x] Xoá các module thừa `vnpt_hrm`, `vnpt_hrm_attendance`, `vnpt_hrm_payroll`, `required-addons/hr_payroll`. Người dùng đã đồng ý ngày 2026-10-09. Trước khi xoá đã kiểm tra: không manifest nào phụ thuộc, không code nào tham chiếu, thư mục sạch (chỉ lệch `.pyc`), DB `gvnn` không cài. Sau khi xoá `gvnn` vẫn nâng cấp và đăng nhập bình thường.
