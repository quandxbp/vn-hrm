# Bàn giao GVNN — 26/10/2026

Nhánh: `feature/edu-gvnn`. Bản source này gom các thay đổi GVNN, Google Video,
giao diện dashboard, thanh chức năng Zalo và hình ảnh Kim Academy từ các phiên gần đây.
Nhật ký chi tiết và đường dẫn backup: [SESSION_HANDOFF_2026-10-24.md](SESSION_HANDOFF_2026-10-24.md).

## Trạng thái local

- Odoo Docker đang chạy tại http://localhost:8069, database `gvnn`, 156 buổi học.
- `edu_gvnn`: **17.0.1.15.3**; `edu_video`: **17.0.1.3.2**.
- `edu_landing`: **17.0.1.9.0**; `edu_zalo`: **17.0.1.2.1**;
  `vnpt_hrm_dashboard`: **17.0.1.1.0**.
- Chưa deploy internet. Push Git không đồng nghĩa đã deploy.
- Workflow Windows có điều kiện `KIM_DEPLOY_ENABLED=true`; hướng dẫn triển khai ở
  [WINDOWS_DEPLOY.md](WINDOWS_DEPLOY.md). Không tự bật runner/deploy trong phiên tiếp theo.

## Lịch giáo viên và Recording

- Link xem công khai: `/weekly-schedule?teacher=zahra`, thêm `&week=102` để xem tuần cũ.
  Mặc định tuần hiện tại theo giờ Việt Nam; không tự lấy tuần cũ khi tuần hiện tại trống.
- Giao diện tiếng Anh, container căn giữa tối đa 1320px, dòng lịch gọn, thứ/ngày có màu riêng.
- Hồ sơ giáo viên có **Link cập nhật Recording** dành riêng cho giáo viên đó.
  Link chứa token bí mật; không ghi token thật vào Git, ảnh thanh địa chỉ hoặc ghi chú.
- Giáo viên điểm danh bằng checkbox vắng và Save; buổi đã chốt lương/hủy khóa điểm danh.
- Recording có **+ Add part**, lưu nhiều link một lần. Save tại chỗ, popup thông báo,
  giữ bản nháp khi lỗi và kiểm tra dữ liệu cũ để tránh ghi đè thay đổi mới.
- Phần 1 giữ nguyên `edu.session.google_drive_url` / `youtube_url` cũ.
  Phần 2 trở đi dùng `edu.session.recording.part`, tối đa 10 phần qua trang giáo viên.
- Giáo viên chỉ cập nhật Drive. Giáo vụ quản lý YouTube trong tab **Video buổi học**.
  Tab đã sửa lỗi bảng đoạn bổ sung bị bó hẹp; đã kiểm tra buổi **30618**.

## Upload YouTube

- Xếp hàng từng đoạn chưa có YouTube; kết quả ghi về đúng phần tương ứng.
  Trạng thái tổng không báo hoàn tất khi còn phần chờ/lỗi.
- Giữ quyền riêng tư mặc định **unlisted**. Chưa làm ghép các đoạn thành một video.
- Chưa thực hiện upload video thật trong phiên này. Kết nối đúng kênh sẽ hoàn tất
  sau khi deploy theo trao đổi với người dùng; không tự đổi kênh hoặc cấp quyền thay họ.
- Chi tiết OAuth: [GOOGLE_VIDEO.md](GOOGLE_VIDEO.md),
  [VIDEO_AUTOMATION.md](VIDEO_AUTOMATION.md).
- Đoạn đã có YouTube hoặc lịch sử upload được bảo vệ khỏi thay/xóa nguồn nhầm.

## Các thay đổi khác trong bản source

- Tạo tuần mới từ tuần cũ; không sao chép kết quả điểm danh/video.
- Nhập lịch sử từ sheet `2.Điểm danh`; xuất theo 28 cột sheet `Weekly`.
  Xuất đủ các URL khi một buổi có nhiều đoạn; thời lượng video vẫn để trống nếu chưa có.
- Chỉnh menu, badge tuần/giáo viên/học sinh, thanh nút và các lỗi điều hướng dashboard.
- Đồng bộ các trang edu_landing; ảnh Kim Academy và nguồn ảnh lưu tại
  `custom-addons/edu_landing/static/src/img/kim/SOURCES.json`.
- Gửi Zalo thủ công hoạt động; tự động 12h vẫn tắt theo trạng thái bàn giao trước.

## Kiểm tra và dữ liệu local

- **68 tests đạt** trên DB sao chép: lịch public, nhiều Recording, ACL/CSRF, lưu nguyên khối,
  dữ liệu cũ, export/clone, OAuth giả lập và upload/resume đúng phần.
- Thay đổi bố cục tab Video sau đó đã qua XML/Odoo view validation và kiểm tra Chrome:
  thêm dòng Phần 2 rồi Discard, desktop/mobile 390px không tràn ngang.
- DB thử nghiệm đã xóa; không lưu video/điểm danh thử vào dữ liệu thật.
- Backup trước chức năng nhiều đoạn nằm ngoài repo:
  `D:\Projects\vn-hrm-backups\recording-parts-20261026\gvnn-preupgrade.dump`.
- JSON OAuth, `.env.zalo`, Excel dữ liệu thật, artifacts, cache và node_modules được loại khỏi Git.
  Máy khác cần DB/filestore và cấu hình riêng; source không chứa dữ liệu vận hành.

Khi cập nhật máy khác: sao lưu DB/filestore trước, nâng cấp các module đã cài
`edu_gvnn,edu_video,edu_landing,edu_zalo,vnpt_hrm_dashboard`, rồi khởi động lại web.
Chỉ nâng cấp `edu_video` nếu module này đã được cài trên DB đích.
