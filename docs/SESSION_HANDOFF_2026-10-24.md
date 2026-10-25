# Bàn giao phiên GVNN và Zalo — 24/10/2026

> **Backend Video tab layout fix — 26/10/2026:** edu_gvnn17.0.1.15.3 + edu_video17.0.1.3.2 upgraded local gvnn.
> Reproduced session30618: additional-parts One2many was squeezed into one narrow group cell.
> Replaced wrapper group with full-width separator + direct field, shortened Part1 labels, and added
> scoped96px minimum header width for part number (Odoo list sizing ignored XML width hint).
> Upload section now has heading/empty message; hidden empty history table removes confusing blank grid.
> Actual session30618 checked: table1631px desktop, all3headers readable; Add line created Part2 draft
> with all inputs editable, then Discard changes used. No saved test rows, links, attendance or uploads.
> Mobile390: document390/table341, no page overflow. Console clean. XML+Odoo upgrade validation passed.
> Screenshot artifacts/session-30618-video-fixed.jpg. Previous68 functional tests still the latest logic tests;
> this fix changes view/layout only. Not committed/pushed/deployed to internet.

> **Multiple recording parts — 26/10/2026:** edu_gvnn17.0.1.15.1 + edu_video17.0.1.3.1 upgraded local gvnn.
> Teacher opens Recording, uses **+ Add part**, fills Part1/Part2... and saves once. Up to10 parts.
> All old links remain in original edu.session.google_drive_url/youtube_url (Part1); no data migration/copy.
> Additional parts use edu.session.recording.part (number>=2, Drive, YouTube), copy=False on session.
> Odoo Video tab has Part1 fields plus editable additional-parts table. Teacher may change Drive only;
> YouTube is maintained by staff or uploader. Public/read-only schedule shows all safe Drive links.
> Multi-save POST retains CSRF/token/ownership checks, validates duplicates (including same file with
> different share parameters), part IDs, URL lengths, max count, and snapshot of all Drive/YouTube pairs.
> Session/part rows locked; savepoint makes all edits atomic. Concurrent changes return409.
> Existing Youtube sources and parts with upload history cannot be silently replaced/removed.
> IDs/numbers remain stable when removing middle parts. Old single-recording POST remains supported.
> Async UI refreshes returned IDs/version/part links, preserves drafts on errors, retains popup/inline saves.
> Additional model ACL only staff (manager inherits); public gains no CRUD rights.
> Uploader queues each unfinished part separately; old jobs without recording_part_id still target Part1.
> Per-part completion/guards/restart write Youtube only to the matching source. Upload button remains
> available when Part1 is uploaded but Part2 is pending. Aggregate state waits for all current parts.
> No video merging implemented; privacy stays configured unlisted; no actual Google download/upload in QA.
> Weekly export keeps28 columns and preserves all multipart URLs (wrapped lines), posted only when every
> part has Youtube. Clone/copy does not carry recording parts. Existing Excel/clone tests retained.
> **68 regression tests passed** in final isolated run (provider/public HTTP, parts, ownership/CSRF,
> stale/atomic saves, export/clone, OAuth mocks and upload/resume/part mapping). TestGoogleConnection fixture
> now clears expected handle in its generic test so it does not inherit local @yuyong90 restriction;
> separate expected-channel test still enforces it. Actual OAuth config was not changed.
> Desktop/mobile390 Add/Remove verified, validation error keeps both fields, no-op save verified. Mobile
> form fills325px within card; no overflow. No business links/attendance changed by UI QA.
> Legacy video fingerprint unchanged during initial upgrade; existing156 sessions preserved,0 new real parts.
> Screenshots artifacts/recording-parts-desktop.jpg and recording-parts-mobile.jpg.
> Backup D:\Projects\vn-hrm-backups\recording-parts-20261026\gvnn-preupgrade.dump (also initial gvnn.dump).
> Isolated test DBs dropped. Not committed/pushed/deployed to internet.

> **Day/date highlight — 26/10/2026:** edu_gvnn17.0.1.14.4. Teacher day headings now use weekday-specific tinted background, matching left accent, stronger date text and a white weekday badge. Keeps centered container and compact rows. XML validated; upgrade local gvnn.

> **Correction: centered container ? 26/10/2026:** edu_gvnn17.0.1.14.3 upgraded local gvnn. User corrected fluid to container. Both schedule views now use responsive .container (540/720/960/1140/1320px maxima), centered, with12px inner gutters. Removed max-width:none overrides. Desktop1920 confirmed1320px width; mobile390 no overflow. Screenshot artifacts/weekly-centered-container.jpg. Compact rows/inline saves unchanged.

> **Container-fluid — 26/10/2026:** edu_gvnn17.0.1.14.2 upgraded local gvnn.
> All schedule content (public and teacher) now shares main.container-fluid; standalone CSS mirrors
> Bootstrap fluid width100% / gutter1.5rem (12px padding per side), without adding Bootstrap dependency.
> Removed conflicting horizontal .schedule padding overrides. Compact rows and inline saves unchanged.
> XML validated; actual desktop1920/mobile390 checked:12px gutters, no horizontal overflow.
> Screenshot artifacts/weekly-container-fluid.jpg. Backup in DB container /tmp/schedule-container-fluid.dump.
> Not committed/pushed/deployed to internet.

> **Compact lesson rows — 26/10/2026:** `edu_gvnn` **17.0.1.14.1**, upgraded local gvnn.
> Teacher desktop uses shared Time / Students / Recording header and compact rows (~51px at1920),
> smaller type/spacing and inline student chips. Explicit Present/Absent remains; tick still means absent.
> Attendance and recording buttons show check + Save with full aria-label/title. Add recording uses plus,
> Edit link uses pencil. Opening Recording stays inline; first live row stayed51px even with input open.
> JS restores cloned button content after async save, preserving check icon; summary icon state refreshes.
> Existing no-navigation Save/toast behavior retained. Mobile390 stacks sections with38px buttons/40px student
> labels and16px link input to prevent zoom. No horizontal overflow at1920/390.
> Four existing HTTP regression tests passed; live unchanged-attendance save verified popup and icon restored.
> No actual attendance/Recording values changed by UI QA. Screenshots artifacts/weekly-compact-desktop.jpg
> and weekly-compact-mobile.jpg. Backup D:\Projects\vn-hrm-backups\schedule-compact-20261026\gvnn.dump.
> Isolated test DB removed. Not committed/pushed/deployed to internet.

> **Full-width schedule + inline saves — 26/10/2026:** `edu_gvnn` **17.0.1.13.1**, upgraded local gvnn.
> Schedule fills available screen width, compact spacing, attendance controls inline on screens>=1600px.
> Standalone public_schedule.js intercepts attendance/recording POSTs using FormData + X-Requested-With.
> Existing HTTP routes retain CSRF/token/ownership/stale checks and return allowlisted JSON for AJAX;
> ordinary form POST fallback remains available. No navigation/replacement of page after Save.
> Success toast fixed top-right auto-dismisses after5s; errors stay until closed. No banner above content.
> Inline saves refresh original_attendance / original_recording so repeated saves do not conflict with themselves.
> Recording link/empty state refresh in place; details stay open. Inputs frozen during request, duplicate
> submission guarded, focused buttons kept focusable with aria-disabled. Network errors retain typed values.
> No-op Recording save now skips ORM write after auth/stale validation.
> 19 distinct model/HTTP tests pass across runs: existing15 model+3HTTP, new AJAX test fixture corrected,
> then all4HTTP passed. Browser verified both Save types, JSON validation error toast, full-width1920,
> mobile390 without overflow. Actual focused-key Save retained scroll2089→2089; desktop707→707.
> UI checks submitted unchanged attendance/empty Recording only; no business values changed.
> Screenshots artifacts/weekly-inline-save-desktop.jpg and weekly-inline-save-mobile.jpg.
> Backup D:\Projects\vn-hrm-backups\schedule-inline-save-20261026\gvnn.dump; test DB removed.
> Not committed/pushed/deployed to internet.

> **Teacher schedule UI redesign — 26/10/2026:** `edu_gvnn` **17.0.1.12.0**, upgraded local gvnn.
> Private editing view uses lesson cards grouped by date: time / attendance / Recording.
> Week and teacher appear once at top. One quick guide replaces repeated row instructions.
> Checkbox still means absent; CSS shows green Present when unchecked and amber Absent when checked.
> Recording form is inside native details: Add recording / Edit link, then Save link.
> No new JavaScript; keyboard accessible labels/details. Public read-only view retains seven-column table.
> No model/controller workflow changes. 3 existing HTTP regression tests passed (public rendering,
> recording save/CSRF and multi-student attendance save/restore). Desktop +390px checked without overflow,
> details opened successfully, console clean. Screenshots artifacts/weekly-schedule-redesign-desktop.jpg
> and weekly-schedule-redesign-mobile.jpg. No real attendance or Recording submitted during UI QA.
> Backup D:\Projects\vn-hrm-backups\schedule-ui-20261026\gvnn.dump; isolated test DB dropped.
> Not committed, pushed or deployed to internet.

> **Teacher attendance — 26/10/2026:** `edu_gvnn` **17.0.1.11.0**, upgraded local gvnn.
> Existing private teacher editing links now allow both Recording and student absence updates.
> Students column: check **Absent**, then **Save attendance**; uncheck to restore present.
> POST `/weekly-schedule/attendance` keeps CSRF, validates token/session/roster ownership,
> locks session and attendees, and detects stale roster or presence state with a snapshot hash.
> Only attendee.present changes; standard charge/payroll recomputes apply. Paid or cancelled
> lessons have locked attendance in both UI and server. Recording remains independently editable.
> Testing/extra participants without actual attendee records remain display-only. Public view remains read-only.
> **18 tests passed**, including anonymous HTTP multi-student absence, restore, CSRF, ownership,
> stale roster/state, billing recompute and paid/cancel guards. Desktop/mobile390 checked without overflow.
> Screenshots artifacts/weekly-attendance-desktop.jpg and weekly-attendance-mobile.jpg.
> Live attendance/Recording unchanged during testing; isolated DB removed. Backup:
> D:\Projects\vn-hrm-backups\schedule-attendance-20261026\gvnn.dump. Not committed or deployed.

> **Weekly schedule English + teacher Recording — 26/10/2026:** `edu_gvnn` **17.0.1.10.0**, upgraded local `gvnn`.
> All public schedule labels, week options, empty/error states and notices are English; names remain original.
> Public `/weekly-schedule?teacher=zahra` stays read-only. Teacher form now has manager-only
> **Link cập nhật Recording** (`schedule_edit_url`); share that private link with the corresponding teacher.
> `/weekly-schedule/edit/<token>` permits Google Drive updates per lesson without login.
> Tokens are independently generated, unique, copy=False, manager-only and initialized once per missing teacher.
> Never put actual editing tokens in documentation, screenshots of address bars, or shared logs.
> POST `/weekly-schedule/recording` keeps CSRF protection, verifies active token/lesson ownership,
> only writes google_drive_url, validates Drive hosts and detects stale edits under row lock.
> Blank clears recording. Recording metadata may be saved after payroll closure via a narrowly scoped
> internal context; existing edu_video job guards/auto-upload behavior remain intact.
> Public pages do not expose tokens or editing controls; no public ACL added to edu.session.
> **13 tests passed**, including anonymous POST/CSRF, cross-teacher denial, stale edits and paid lesson metadata.
> Desktop and mobile390 checked; private week picker tested (102→101); public actual no-cookie request200.
> CSS version query prevents stale styles. Screenshots: artifacts/weekly-recording-desktop.jpg and mobile.jpg.
> Business DB still156 lessons; no real Recording changed by tests. Isolated test DB dropped.
> Backup: D:\Projects\vn-hrm-backups\schedule-recording-20261026\gvnn.dump. Not deployed or committed.

> **Lịch dạy public — 25/10/2026:** `edu_gvnn` **17.0.1.9.0**, đã upgrade DB gvnn.
> URL `/weekly-schedule?teacher=zahra`, không cần đăng nhập. Có thể thêm `&week=102`.
> Mặc định tuần hiện tại theo Asia/Ho_Chi_Minh; nếu chưa có tuần hiện tại thì hiển thị
> tuần thứ Hai–Chủ nhật hiện tại với lịch trống, không tự lấy tuần cũ và không tạo tuần mới.
> Bộ chọn tuần lấy các tuần giáo viên có buổi học, kèm tuần hiện tại/được chọn.
> 7 cột: Tuần, Ngày, Thứ, Giáo viên, Giờ học (VN), Học sinh, Recording.
> Recording CHỈ từ google_drive_url; không lấy youtube_url/recording_url cũ. Drive trống
> hoặc URL không phải http(s) trên drive.google.com/docs.google.com thì không xuất hyperlink.
> Giữ buổi nghỉ (đánh dấu), học viên vắng và testing; thiếu cả hai giờ thì Chưa có giờ.
> Thêm field computed `edu.teacher.public_schedule_url` trong hồ sơ giáo viên để sao chép link.
> Controller auth=public, GET, standalone HTML/CSS (không phụ thuộc Website/edu_landing).
> Provider private `_get_values` chỉ sudo truy vấn đúng teacher active, tên normalize khớp chính xác;
> trả dict allowlist, không truyền recordset sudo ra QWeb. KHÔNG thêm public ACL cho edu.session.
> Không xuất học phí/lương/ghi chú nội bộ/contact. Header no-store, noindex/nofollow và no-referrer.
> 404 khi thiếu/sai/ẩn giáo viên hoặc tuần không tồn tại; 400 nếu số tuần không hợp lệ.
> **9 tests đạt** (8 model + 1 HTTP anonymous); test HTTP chạy lại sau thêm HTML5 doctype đạt.
> Đã gọi actual URL không cookie: HTTP200 không login. Chrome đã xem Zahra (18 buổi tuần102),
> đổi tuần100, kiểm tra 390px hiển thị dạng thẻ không tràn ngang và reset viewport.
> Ảnh `artifacts/public-weekly-zahra.jpg`, `public-weekly-zahra-mobile.jpg`.
> DB nghiệp vụ vẫn 156 buổi; DB test đã xóa. Backup
> `D:\Projects\vn-hrm-backups\public-schedule-20261025\gvnn.dump`. Chưa deploy internet.

> **Thanh nút buổi học gọn hơn — 25/10/2026:** `edu_gvnn` **17.0.1.8.1**,
> `edu_zalo` **17.0.1.2.1**, đã upgrade local. Bỏ chữ Chức năng đầu thanh.
> Bên trái: Tạo tuần mới (fa-calendar-plus-o), Gửi Zalo (fa-paper-plane).
> Bên phải: Nhập lịch sử (fa-upload), Xuất điểm danh (fa-file-excel-o).
> Hai nút file có class `edu_session_action_file`; controller chia headerButtons thành
> main/files, template render hai nhóm, files dùng margin-inline-start:auto.
> Giữ ACL và action cũ; tooltip Gửi Zalo vẫn giải thích gửi ngay lịch HÔM NAY theo giờ VN.
> Đã kiểm tra Chrome: đúng vị trí/icon, mở/đóng 3 wizard, console không lỗi.
> 390px tự xuống hai hàng, không tràn ngang; đã reset viewport. Không bấm gửi Zalo,
> không tạo tuần, không nhập dữ liệu. Ảnh `artifacts/session-toolbar-compact.jpg`.
> Backup `D:\Projects\vn-hrm-backups\session-toolbar-20261025\gvnn.dump`.

> **Nhập lịch sử tại list buổi học — 25/10/2026:** `edu_gvnn` **17.0.1.8.0**, đã upgrade local.
> `menu_edu_import` inactive, không xóa ID/action. Nút manager **Nhập lịch sử buổi học**
> nằm đầu toolbar edu.session, mở `action_edu_import_wizard`. `import_views.xml` nạp
> trước `session_views.xml` để action được tham chiếu, menu legacy chỉ là record inactive.
> Wizard mặc định `import_mode=attendance`: chỉ cần sheet 2.ĐIỂM DANH (tên không phân biệt
> hoa/thường/khoảng trắng); ngày từ/đến tùy chọn, trống là toàn bộ lịch sử kể cả trước 2026.
> Không đọc các sheet học phí/danh mục, không nhập phiếu thu/số dư đầu kỳ/đơn giá/kỳ lương.
> Danh mục còn thiếu được tạo từ dòng học: giáo viên/lớp/học viên; HV mới Ngưng học,
> không đổi trạng thái HV đã tồn tại. Bỏ qua marker TESTING/SPEAKING khi tạo HV.
> Chế độ `all` giữ luồng tổng hợp nâng cao cũ, yêu cầu ngày bắt đầu.
> Giờ, buổi nghỉ, testing, ONLY attendance, ghi chú, Recording/YouTube được giữ;
> sửa đọc điểm đúng W/X (SCORE STUDENT 1/2), trước đây chỉ đọc X làm điểm đầu tiên.
> Chống nhập lại theo import_key, thêm key ngay khi xếp batch; wizard đã có result không chạy lại.
> Advisory transaction lock serialize import. Luôn cleanup _STATES trong finally.
> Lịch sử tạo tuần theo thứ Hai xuất hiện nhiều nhất trong toàn bộ dữ liệu của số tuần;
> ngày ngoài khoảng tuần hoặc tuần không tạo được được báo rõ dòng và bỏ qua, không ép
> ngày vào tuần sai. File nguồn có một số dòng sai ngày/số tuần và vài ONLY không khớp tên;
> các cảnh báo đó hiển thị trong kết quả, người dùng cần kiểm tra Excel.
> **13 tests đạt**: 6 history mới + 4 export + 3 video. Test cả sheet đơn, ngày 2001,
> lọc ngày, chống trùng, canceled/testing, 2 điểm, cột video và các lỗi nguồn.
> Đã thử file TỔNG HỢP_GVNN.xlsx thật trên DB bản sao: 5.648 buổi tạo, 18 dòng lỗi/bỏ qua,
> 24,16 giây; phiếu thu/kỳ lương/đơn giá không tăng. Sau đó rollback, xóa DB test.
> Báo cáo local `artifacts/history-import-report.json`, log `history-import-real-file.log`.
> **KHÔNG nhập dữ liệu quá khứ lên DB gvnn thật**; DB thật vẫn 156 buổi.
> Chrome đã mở nút/wizard, mode/ngày mặc định đúng; ảnh `artifacts/session-history-import.jpg`.
> Backup: `D:\Projects\vn-hrm-backups\history-import-20261025\gvnn.dump`.

> **Xuất điểm danh theo Weekly — 25/10/2026:** `edu_gvnn` **17.0.1.7.0**, đã upgrade local.
> Wizard `edu.export.week.wizard` nay xuất sheet **Weekly**, 28 cột A–AB, header dòng 1,
> dữ liệu từ dòng 2. Tên header khớp nguyên văn (kể cả xuống dòng/khoảng trắng) sheet
> Weekly của file local `Điểm Danh_GVNN .xlsx`. Bỏ bố cục cũ 2.ĐIỂM DANH và AH/AI.
> Q = 1 Đã dạy / 0 Nghỉ; T = completion_note + học viên vắng; U = note;
> W = 1 nếu có YouTube hoặc video_posted cũ; X–Y = tối đa 2 link khác nhau theo ưu tiên
> YouTube → Drive → Recording cũ. Z–AB điểm theo thứ tự học viên, người tham gia khác
> có thể vào ô học viên còn trống. Không xuất PAID vì mẫu Weekly không có cột này.
> P/R/S (Padlet) chưa có field nên trống. **V là thời lượng video**, người dùng đã xác nhận
> để trống khi chưa có dữ liệu; KHÔNG lấy minutes hoặc thời gian buổi học thay vào đó.
> N/O giữ giờ tính học viên/giáo viên trong Odoo, không tính lại theo khung giờ.
> P–S ẩn mặc định theo mẫu (có thể Unhide), freeze F/row1, autofilter A:AB.
> Ngày/giờ là giá trị Excel đúng kiểu; link bấm được; tắt strings_to_formulas để ghi chú
> bắt đầu bằng = vẫn là chữ. Giữ helper _video_values cho tương thích và test video cũ.
> **7 tests đạt** trên DB bản sao: 4 export mới + 3 video cũ. DB test đã xóa.
> Đã click Xuất Excel từ toolbar edu.session: file tuần 102 có 53 buổi, so khớp toàn bộ
> 28 header với file gốc, cột V trống. Mẫu `artifacts/weekly-export-102.xlsx`,
> ảnh `artifacts/weekly-export-dialog.jpg`. Không đổi dữ liệu buổi học/học phí/lương.
> Backup: `D:\Projects\vn-hrm-backups\weekly-export-20261025\gvnn.dump`.

> **Sửa click Dashboard + bố cục:** `vnpt_hrm_dashboard` **17.0.1.1.0**, đã upgrade local.
> Lỗi Invalid handler do 4 KPI tài chính có `t-on-click="kpi.onClick"` nhưng thiếu hàm.
> Cả 5 KPI nay là button có handler: học viên đang học; tiền thu/tổng chi/dòng tiền mở
> pivot `edu.report.finance` theo năm và nguồn tương ứng; số dư mở học viên đang học.
> Lối tắt Cảnh báo học viên mở danh sách thay vì wizard. 7 cảnh báo dùng button,
> có guard thiếu tuần; tên trong bảng ưu tiên mở hồ sơ theo student_id.
> Hero có icon; KPI chữ gọn, focus bàn phím, lối tắt trải đều một hàng; cảnh báo và bảng
> ưu tiên cạnh nhau trên desktop, xếp dọc khi hẹp. Không thêm gửi tin hoặc hành động tài chính.
> Đã click thử Chrome: 5 KPI + 7 cảnh báo + 7 lối tắt + 1 hồ sơ học viên (20 đường mở),
> đóng wizard xuất mà không xuất/tạo dữ liệu. Console sau sửa không có lỗi.
> Local thu/chi đang bằng 0 nên pivot tài chính hiển thị No data, đây là trạng thái dữ liệu;
> chưa kiểm tra biểu đồ thu chi có số khác 0 trong lượt này. Biểu đồ cảnh báo hiện được.
> Backup `D:\Projects\vn-hrm-backups\dashboard-fix-20261024\gvnn.dump`;
> ảnh `artifacts/gvnn-dashboard-fixed.jpg`. Chưa commit/push.

> **Đồng bộ giao diện GVNN:** `edu_gvnn` **17.0.1.6.0**, đã upgrade DB `gvnn`.
> SCSS dùng chung `static/src/scss/gvnn_ui.scss`, giới hạn trong `.edu_form` / `.edu_list`.
> Hồ sơ học viên, giáo viên, lớp có tiêu đề + icon; buổi học có tiêu đề riêng.
> Các nhóm thông tin có tên rõ ràng, tab nền nhẹ, số dư và đơn giá có điểm nhấn.
> Cảnh báo học phí và trạng thái dùng badge, bỏ tô đỏ/vàng cả dòng học viên;
> buổi học chuyển cảnh báo sang badge, giữ dòng nghỉ mờ và buổi testing màu thông tin.
> Bảng tuần, thu học phí, kỳ lương, danh mục chi phí và cảnh báo dùng style chung.
> Điện thoại/email trên hồ sơ dùng widget liên hệ. Không sửa logic hay dữ liệu nghiệp vụ.
> Kiểm tra XML và 16 view kết hợp qua ORM đạt; mở danh sách buổi học/giáo viên/học viên,
> form giáo viên/học viên trong Chrome. 156 buổi giữ nguyên. Ảnh local:
> `artifacts/gvnn-teacher-polish.jpg`. Backup: `D:\Projects\vn-hrm-backups\ui-polish-20261024\gvnn.dump`.
> Khi reload từ action dashboard cũ có console Invalid handler một lần lúc khởi tạo;
> không có lỗi nâng cấp/view/SCSS. Log bus_presence có serialization conflict lúc stop web.

> **List theo tuần và thẻ học viên:** `edu_gvnn` **17.0.1.5.1**. Cột Tuần đứng đầu,
> widget `edu_session_week` có số tuần + khoảng ngày và màu ổn định. Action Buổi học
> mặc định nhóm theo tuần (`search_default_group_week=1`), mở sẵn (`expand=1`), mới nhất
> trước: local 102 → 101 → 100. `week_id asc` trong default_order là có chủ ý vì
> model `edu.week` đã `_order='number desc'`; đổi desc sẽ đảo nhóm về tuần cũ trước.
> Tên học viên dùng widget `edu_session_students`, mỗi HV một thẻ, tên Việt dòng trên,
> tên Anh nhỏ phía dưới, người nghỉ có nhãn Nghỉ. JSON computed `student_badge_data`
> chỉ phục vụ render; `student_names` và dữ liệu export/điểm danh không đổi.
> Renderer riêng của list ẩn tổng time_start/time_end ở đầu nhóm; KHÔNG đổi group_operator
> của hai field vì Odoo cần aggregator để sort group. Tổng học phí/lương vẫn giữ.
> Đã kiểm tra Chrome: đúng thứ tự cột/nhóm, tên tách dòng, không có lỗi console.

> **Menu theo luồng công việc (bản chốt mới hơn):** `edu_gvnn` **17.0.1.5.0**.
> 5 nhóm: **Lịch học** (Buổi học, Tuần học, Video buổi học), **Danh mục** (học viên,
> lớp, giáo viên), **Tài chính** (thu học phí, kỳ lương, chi phí), **Báo cáo** (cảnh báo
> học viên, tổng quan tài chính, học phí, lương), **Cấu hình** (Thiết lập chung / Kết nối
> dịch vụ / Dữ liệu). Zalo và Google nằm trong Kết nối dịch vụ; Excel trong Dữ liệu.
> Menu xuất điểm danh và wizard cảnh báo cũ đặt inactive, không xóa action.
> Xuất điểm danh vẫn trên thanh Chức năng của buổi học; danh sách cảnh báo có nút
> **Cập nhật cảnh báo tuần** mở wizard. Báo cáo cho staff vào được cảnh báo như trước;
> các báo cáo tài chính vẫn giới hạn manager riêng từng menu và ACL.
> Đã kiểm tra cấu trúc menu, action và view trên server + mở/đóng wizard trong Chrome;
> không thực hiện tạo cảnh báo/gửi lịch. Các ghi chú menu 6 nhóm dưới đây là lịch sử.

> **Bỏ nhập liệu video trùng:** `edu_gvnn` **17.0.1.4.1**. Bỏ Recording và Đã đăng video
> khỏi tab Ghi chú, dùng tab Video buổi học làm nơi nhập link Drive/YouTube.
> 70 Recording cũ đều là youtu.be, được post-migration đưa sang `youtube_url` nếu còn trống,
> không ghi đè link đã nhập, không sửa paid/giá/lương và không tạo job upload.
> Hai cột legacy vẫn giữ trong DB cho tương thích Excel, gắn nhãn Excel cũ.
> Import mới nhận link Recording YouTube vào trường YouTube; export ưu tiên YouTube,
> rồi Drive, rồi Recording cũ; cột POSTED VIDEO đánh OK nếu có YouTube hoặc dấu legacy.
> **17 tests GVNN + 23 tests video đạt** trên DB bản sao. Backup trước chuyển dữ liệu:
> `D:\Projects\vn-hrm-backups\legacy-video-cleanup-20261024\gvnn.dump`.

> **Menu và icon:** `edu_gvnn` **17.0.1.4.0**, tên module và app root là **GVNN**.
> Thanh điều hướng: Lịch học / Học viên / Giáo viên (mở thẳng danh sách) / Tài chính /
> Báo cáo / Cấu hình. Lịch học chứa Buổi học, Tuần học, cảnh báo, xuất điểm danh,
> Gửi lịch Zalo, Video buổi học. Tài chính chứa Thu học phí, Kỳ lương giáo viên, Chi phí khác.
> Giữ quyền manager cho kỳ lương/chi phí/báo cáo và quyền system cho kết nối Google.
> Icon sách + mũ tốt nghiệp tại `static/description/icon.svg` và `icon.png`;
> script dựng lại PNG: `scripts/render_gvnn_icon.py` (Pillow). Đã nâng cấp local
> `edu_gvnn,edu_zalo,edu_video` và kiểm tra menu/icon trên Chrome.

> **Badge giáo viên:** `edu_gvnn` **17.0.1.3.2**. Cột `teacher_id` của list
> `edu.session` dùng widget `edu_teacher_badge`, nền nhẹ, viền mảnh, bo góc 6px.
> Màu ổn định theo ID giáo viên với bảng 8 màu, sử dụng biến màu theme.
> File `static/src/fields/teacher_badge.js` và `.scss`; các màn hình giáo viên khác không đổi.
> Đã nâng cấp local và kiểm tra Chrome: badge render đúng, màu nhất quán, console không lỗi.

> **Chốt yêu cầu sao chép:** `edu_gvnn` **17.0.1.3.1**, chỉ còn **tạo tuần mới**
> từ tuần nguồn, đã bỏ chế độ sao chép vào tuần có sẵn và trường chọn chế độ trên UI.
> **Lấy cả lịch của buổi đã nghỉ mặc định True**; vẫn có thể bỏ tick.
> Buổi mới của cả lịch đã nghỉ vẫn mặc định Đã dạy/Có mặt, không giữ trạng thái nghỉ cũ.
> Trường `target_week_id` chỉ lưu tuần đã tạo để xem kết quả. Nút này cần quyền Quản lý GVNN.
> 14 tests clone cập nhật đều đạt, không tạo tuần/lịch thật trong phiên này.

> **Tạo tuần mới từ lịch cũ:** `edu_gvnn` **17.0.1.3.0** bổ sung chế độ mặc định
> **Tạo tuần mới** trong Sao chép lịch tuần. Chọn nguồn bất kỳ; số tuần/ngày mới
> mặc định nối tiếp tuần mới nhất (local: nguồn 102 → mới 103, 26/10–01/11/2026).
> Có thể chỉnh số tuần và ngày bắt đầu, hoặc chọn chế độ Tuần đã có như trước.
> Tạo tuần và toàn bộ lịch trong một savepoint: lỗi/chốt lương không để lại tuần rỗng;
> chặn trùng số tuần, trùng ngày và bấm lặp. Tạo tuần mới cần quyền Quản lý GVNN,
> nhân viên vẫn sao chép vào tuần đã có. **14 tests clone + 23 tests video đạt**.
> Không tự tạo tuần 103 trên dữ liệu thật; người dùng bấm Sao chép lịch để thực hiện.

> **Bố cục list buổi học:** `edu_gvnn` **17.0.1.2.1**. Các nút Sao chép lịch tuần,
> Xuất điểm danh tuần và Gửi lịch hôm nay nằm trong hàng **Chức năng** riêng dưới control panel,
> trên bảng dữ liệu. Chỉ list `edu.session` dùng `js_class="edu_session_list"`;
> không patch controller chung. Các nút vẫn dùng `MultiRecordViewButton` của Odoo và
> thông tin quyền/action từ XML gốc. File JS/XML/SCSS tại `static/src/views/session_list.*`.
> Đã kiểm tra trực tiếp Chrome: render đúng, console không có lỗi, mở/đóng wizard sao chép được;
> không gửi Zalo hay tạo lịch trong kiểm tra. Ảnh tại `artifacts/session-action-bar.jpg` (gitignore).

> **Sao chép lịch tuần:** `edu_gvnn` **17.0.1.2.0** đã nâng cấp local. Nút
> **Sao chép lịch tuần** luôn hiện trên list `edu.session`, mở wizard chọn tuần nguồn bất kỳ
> và tuần đích sau đó (tuần đích đủ 7 ngày; có thể tạo tuần mới bằng quyền quản lý).
> Giữ thứ/giờ/GV/lớp/học viên; tùy chọn lấy lịch buổi nghỉ. Buổi mới mặc định Đã dạy,
> học viên Có mặt, score reset, giá học viên theo mặc định hiện tại, giá GV theo ngày mới.
> Không sao chép ghi chú kết quả, video, import key, paid hoặc hàng đợi upload.
> Bỏ qua lịch trùng đúng ngày/giờ/GV/loại/lớp/học viên; nguồn và đích hiện có không sửa.
> Chặn tháng đích đã chốt lương; nguồn đã chốt vẫn đọc để sao chép được.
> **10 tests clone + 23 tests video đạt** trên DB bản sao. Chưa sao chép lịch thật.
> Backup trước nâng cấp: `D:\Projects\vn-hrm-backups\clone-week-20261024\gvnn.dump`.

> Bổ sung Google Video: xem [GOOGLE_VIDEO.md](GOOGLE_VIDEO.md). Module `edu_video`
> **17.0.1.2.0** đã cài local, có tải Drive / resumable upload YouTube,
> hàng đợi, retry/hủy/kiểm tra trùng và callback cấu hình theo domain. **23 tests mocked đạt**.
> Xử lý nền và tự xếp hàng tắt. Xem [VIDEO_AUTOMATION.md](VIDEO_AUTOMATION.md).
> Người dùng muốn deploy rồi nhờ chủ kênh AU KIM NGAN @YUYONG90 cấp OAuth
> (quyền mời qua Studio không hỗ trợ API). Chưa upload thật. Link Drive và YouTube riêng
> trên buổi học đã được bổ sung trong `edu_gvnn` 17.0.1.1.1.

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
