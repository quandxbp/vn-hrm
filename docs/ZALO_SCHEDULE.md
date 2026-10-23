# Gửi lịch học qua Zalo cá nhân

Module `edu_zalo` lấy lịch từ `edu.session`. Dịch vụ `services/zalo-bridge` dùng
`zca-js` 2.1.2 để đăng nhập QR và gửi tin vào một nhóm được xác nhận.
Không cần Telegram, không tự đọc hoặc sao chép tin nhắn trong các cuộc trò chuyện.

## Cài đặt

1. Tạo `.env.zalo` theo `.env.zalo.example`, thay khóa bằng chuỗi ngẫu nhiên ít nhất 32 ký tự.
2. Chạy `docker compose --profile zalo up -d --build zalo-bridge`.
3. Cài `edu_zalo` trên đúng DB nghiệp vụ. Không cài đồng thời vào nhiều DB dùng chung bridge.
4. Đặt system parameters `edu_zalo.bridge_url=http://zalo-bridge:3000` và
   `edu_zalo.bridge_token` bằng khóa trong `.env.zalo` (không commit hoặc in khóa vào log).
5. Vào **Trung tâm GVNN → Vận hành → Lịch học Zalo**.
6. Bấm **Đăng nhập bằng QR**, chờ vài giây rồi bấm **Cập nhật kết nối / QR**.
   Quét QR trong Zalo điện thoại và xác nhận, sau đó cập nhật lần nữa.
7. Chọn nhóm và bấm **Xác nhận nhóm nhận**. Xem trước ngày gửi, thử **Gửi lịch**.
   Tin được xếp hàng và xử lý trong khoảng một phút; xem kết quả trong Lịch sử gửi.
8. Sau khi thử đúng nhóm, bật **Tự động gửi lúc 12:00 mỗi ngày** và lưu.

Trên danh sách Buổi học, nút **Gửi lịch hôm nay** gửi trực tiếp toàn bộ lịch của ngày
hiện tại theo giờ Việt Nam vào nhóm đã xác nhận, không phụ thuộc bộ lọc hoặc dòng được
chọn. Thông báo hiển thị kết quả ngay sau khi cầu nối phản hồi. Mỗi lần chủ động gửi
sau một lần gửi thành công sẽ tạo tin mới với nội dung lịch hiện tại. Màn hình
Lịch học Zalo vẫn dùng để xem trước/chọn ngày khác.

## Hành vi

- Mốc giờ `Asia/Ho_Chi_Minh`, khoảng chạy 12:00–12:30. Nếu máy chủ tắt suốt khoảng đó,
  lịch hôm đó không tự gửi muộn; dùng gửi thủ công nếu cần.
- Lấy các buổi của đúng ngày, bỏ buổi đã hủy, sắp theo giờ; hiển thị giáo viên,
  học viên có mặt. Danh xưng Thầy/Cô và Link học cấu hình tại hồ sơ Giáo viên.
  Gom các tiết theo từng giáo viên, mỗi đoạn có tên Thầy/Cô, đủ từng khung giờ
  và học viên tương ứng; link học đặt cuối ngay đoạn của giáo viên đó.
  Các đoạn xếp theo tiết đầu tiên trong ngày; các tiết trong đoạn xếp theo giờ.
  Giáo viên thiếu link hiển thị “CHƯA CẤU HÌNH LINK HỌC”. Chưa chọn danh xưng thì dùng GV.
  Không gửi học phí, lương hoặc thông tin phụ huynh.
- Dùng cỡ chữ mặc định của Zalo. Tiêu đề lịch in hoa; tên giáo viên viết hoa,
  danh xưng giữ dạng Thầy/Cô. Tiêu đề và tên giáo viên in đậm, màu xanh lá.
  Dòng giờ và nhãn LINK HỌC in đậm.
  Danh xưng hiển thị Thầy/Cô; mỗi tiết một dòng `17:30–18:00: TÊN HỌC VIÊN`.
  Các tiết cùng giáo viên liền nhau, chỉ cách một dòng trống giữa hai giáo viên.
  URL giữ nguyên ký tự và cách viết hoa/thường. Định dạng được gửi bằng `styles`
  của Zalo, áp dụng cho từng phần tin sau khi chia, không dùng HTML/Markdown.
- Gửi tự động chỉ một lần mỗi ngày/nhóm; gửi thủ công được gửi lại sau khi thành công.
  Mỗi yêu cầu có mã riêng để chống lặp khi thử lại do lỗi kết nối.
  Nội dung đã xếp hàng được giữ nguyên; lần gửi thủ công mới lấy nội dung mới nhất.
- Tin dài được chia tối đa 1800 ký tự/phần; bridge chấp nhận tối đa 20 phần.
- Bridge lưu mã yêu cầu và kết quả trên volume `zalo-bridge-data` trước/sau gửi.
  Gọi lại cùng mã trả kết quả cũ. Nếu mất kết nối đúng lúc gửi hoặc tiến trình bị dừng,
  trạng thái là **Cần kiểm tra trên Zalo**, không tự gửi lại vì có thể đã tới nhóm.
- Lỗi kết nối cho phép thử lại với cùng mã; bridge vẫn chống trùng.
- Token API và phiên Zalo nằm trong cấu hình riêng/volume. API không mở cổng ra máy chủ.
  Chỉ Quản lý GVNN được thao tác trong Odoo.

Đây là API Zalo không chính thức. Khi phiên hết hạn, quét QR lại. Cần sao lưu
volume chứa cả phiên và sổ gửi cùng với DB; không xóa volume để restart dịch vụ.

## Kiểm tra

`docker run --rm -v "<repo>/services/zalo-bridge:/app:ro" -w /app node:22-alpine npm test`
kiểm tra API xác thực, đúng nhóm, chống trùng đồng thời, khôi phục sau restart và timeout.

Odoo: chạy trên DB thử với `--test-enable --test-tags /edu_zalo --stop-after-init --no-http`.
Các test dùng cầu nối giả, không gửi tin thật lên Zalo.
