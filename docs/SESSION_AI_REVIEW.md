# Nhận xét AI buổi học

Addon: `edu_session_review`, phụ thuộc `edu_video`. Chỉ quản lý GVNN xem/tạo/hủy báo cáo.
Không chấm điểm hay tự quyết định đánh giá nhân sự.

## Cấu hình

1. Cài addon, vào **Cấu hình → Kết nối dịch vụ → Google Drive / YouTube**.
2. Nhập API key Gemini bằng ô mật khẩu và lưu. Ô này không đọc lại giá trị key đã lưu.
   Không đưa key vào Git, file cấu hình trong repo hay log. API key riêng với OAuth Google.
3. Chọn model có video + JSON structured output; mặc định `gemini-3.5-flash-lite`.
   Bấm **Kiểm tra kết nối Gemini** để kiểm tra key/model; nút này chỉ đọc metadata model,
   không khẳng định hạn mức hoặc khả năng phục vụ inference tại mọi thời điểm.
4. Kết nối Drive, bật **Cho phép phân tích Gemini**. Bật tùy chọn tự động nếu muốn xử lý
   khi gắn/thay link. Việc bật gửi video đến Google Gemini; thống nhất phạm vi sử dụng dữ liệu
   và điều khoản dự án Google trước khi bật. Không cần công khai video.
5. Mặc định tối đa 10 phần, tổng 1024 MB và 120 phút. Cron chạy mỗi phút.

## Sử dụng

Mở buổi học → **Nhận xét AI** → **Phân tích / phân tích lại**. Mở **Xem nhận xét** để đọc:
thời lượng video, thời gian dạy/học ước lượng, mức tương tác, nhận xét chung,
điểm mạnh và điểm cần cải thiện có dẫn chứng `Phần N mm:ss–mm:ss`.

Từ tiêu chí **2.0**, báo cáo gồm bốn phần chính:

1. Thời gian giảng dạy / tổng video theo `phút:giây`, tỷ lệ và mốc giáo viên thực sự bắt đầu dạy.
   Loại chờ học sinh, kiểm tra thiết bị, chuẩn bị và gián đoạn ngoài bài; học sinh luyện tập
   và suy nghĩ có chủ đích vẫn thuộc hoạt động giảng dạy. Nhiều video được cộng các khoảng hợp lệ.
2. Nội dung thực tế đã dạy: chủ đề, từ/cấu trúc nghe rõ, kỹ năng và hoạt động, có mốc dẫn chứng.
3. Nhận xét chất lượng, ưu điểm và góp ý kèm hành động cải thiện cụ thể.
4. Điểm /10 do server cộng từ bốn tiêu chí /2,5: nội dung, hướng dẫn/sửa lỗi, tương tác,
   tổ chức/thời gian. Từng điểm có lý do và dẫn chứng; thiếu dữ liệu thì để chưa chấm, không gán 0.

Schema gửi Gemini bỏ các ràng buộc độ dài mảng lồng nhau để tránh lỗi `INVALID_ARGUMENT`
ở bộ tạo structured output. Giới hạn nội dung/ưu điểm/góp ý/dẫn chứng vẫn được kiểm tra
tại server trước khi công bố báo cáo; không bỏ kiểm tra dữ liệu.

Báo cáo cũ được giữ nguyên và ghi rõ chưa có tiêu chí mới. Bấm **Phân tích lại** để tạo
phiên bản mới; không tự chấm thêm điểm cho nhận xét cũ hoặc tự chạy lại toàn bộ video.

## Xem trên lịch tuần của giáo viên

- Lịch tuần có cột **YouTube**, liệt kê link hợp lệ của tất cả phần video theo số phần.
- Cột **Actions** có nút icon **Session Review**. Trên link cập nhật riêng của giáo viên,
  nút mở modal đọc nhận xét mới nhất: tổng kết, nội dung đã dạy, thời gian, ưu điểm/góp ý,
  điểm từng tiêu chí, căn cứ chấm điểm, tương tác, chất lượng bản ghi và nguồn video.
- Link công khai chỉ hiện link YouTube; nút đọc nhận xét bị vô hiệu hóa. Nội dung AI
  không được nhúng vào HTML lịch, chỉ tải khi mở modal bằng token đúng giáo viên/buổi học.
- Endpoint POST `/weekly-schedule/session-review` kiểm tra CSRF, token giáo viên đang hoạt động
  và quyền sở hữu buổi học. Phản hồi không cache, không trả lỗi nội bộ hay JSON thô của AI.
- Mở modal chỉ đọc kết quả đã lưu, không chạy lại AI hoặc sửa điểm danh/link video.

Hoạt động dạy/học tính cả học sinh luyện tập, sửa lỗi và thời gian suy nghĩ có mục đích;
không đồng nhất với thời gian giáo viên nói. Thời lượng video lấy từ metadata Gemini,
tổng hoạt động được tính từ các khoảng hợp lệ, không chồng lặp. Thiếu dữ liệu thì ẩn tỷ lệ,
không ép điểm hoặc tự suy đoán. Quản lý cần kiểm tra dẫn chứng trước khi dùng nhận xét.

Tự động chỉ xếp hàng link mới/thay đổi, không quét video cũ. Tác vụ không phụ thuộc việc
đã có YouTube và không cản upload. Nhiều phần được phân tích chung. Thay link đánh dấu
báo cáo cũ không còn khớp; phân tích lại tạo phiên bản mới. File Drive bị sửa nhưng giữ nguyên
URL cần bấm phân tích lại thủ công. Không tự phát hiện chỉnh sửa trên Drive.

## Vận hành

- File tải từ Drive được xác minh MD5, tải/upload từng khối, nối lại bằng offset phía Gemini.
  Cache riêng `data_dir/edu_session_review/<database hash>/<part id>.video`, không dùng hay xóa
  cache YouTube/filestore. File local được xóa sau khi Gemini nhận file.
- Khi xong/lỗi/hủy, dọn file trên Gemini; nếu lỗi thì ghi `cleanup_pending` để cron thử lại.
  Tác vụ quá 24 giờ bị dừng và dọn cache, kể cả khi phân tích đang tắt. Không xóa Drive/YouTube.
- Gemini generateContent chạy trong worker, không giữ cuộc hội thoại Interactions.
  Việc xử lý dữ liệu phía nhà cung cấp vẫn theo điều khoản và cấu hình dự án Google.
- HTTP quá tải/hạn mức được thử lại tối đa 3 lần. Yêu cầu phân tích mất phản hồi không
  được gửi lại tự động vì có thể phát sinh chi phí trùng; tạo lần phân tích mới sau khi kiểm tra.
- Mỗi báo cáo lưu người yêu cầu, model, phiên bản prompt, link nguồn và kết quả đã xác thực.
  Từ prompt 1.1, AI trả mốc `MM:SS`; server quy đổi sang giây và kiểm tra giới hạn video,
  tránh nhầm `29:46` thành 2946 giây. Kết quả JSON bị từ chối cũng được lưu nội bộ để chẩn đoán,
  không hiển thị thành báo cáo hợp lệ và không tự gửi lại yêu cầu phân tích.
- Database neutralized không chạy gửi video. Môi trường local sao chép production vẫn cần
  kết nối Drive riêng; không tự sao chép OAuth/token production vào local.
- Các bài test dùng mock mạng và thư mục tạm; không dùng video học sinh hoặc key thật.
