# Nhận xét AI buổi học

Addon: `edu_session_review`, phụ thuộc `edu_video`. Chỉ quản lý GVNN xem/tạo/hủy báo cáo.
Không chấm điểm hay tự quyết định đánh giá nhân sự.

## Cấu hình

### Xử lý lỗi kết nối (02/11/2026)

Từ `17.0.2.2.1`, lỗi ghi rõ bước Drive/upload/chờ phân tích/kiểm tra kết quả và
loại lỗi kỹ thuật, không ghi khóa, URL phiên upload hay nội dung exception mạng.
Upload Gemini chia 4 MiB, tiếp tục từ offset máy chủ xác nhận, chờ tối đa 90 giây
mỗi request tải chunk. Inference chờ tối đa 180 giây; Odoo dành 300 giây cho cron,
giữ nguyên giới hạn HTTP. Không dùng timeout cron ngắn hơn request inference.

Lỗi trước inference tiếp tục theo cơ chế thử lại giới hạn. Mất phản hồi sau khi
đã gọi inference giữ cờ chưa xác nhận, không tự lặp yêu cầu có thể tính phí.
Phản hồi inference đã nhận được giữ riêng để kiểm tra nếu JSON kết quả không hợp lệ.
Không tự chạy lại các bản ghi cũ đang lỗi chỉ vì nâng cấp module.

Từ `17.0.2.2.2`, nhận định không thấy học sinh thiếu dẫn chứng từng phần sẽ được
hạ thành chưa xác định/cần đối chiếu; không công bố là vắng. Cờ có mặt từ đầu video
mâu thuẫn với mốc xuất hiện sẽ không được dùng để suy ra giờ vào lớp. Những trường
hợp này không làm mất phần đánh giá giáo viên đã có dẫn chứng hợp lệ. Vẫn từ chối
sai danh tính, mốc vượt video và cảnh báo trễ/tập trung không có căn cứ. JSON gốc
được giữ nguyên; có thể kiểm tra lại kết quả đã lưu mà không gọi Gemini thêm lần nữa.

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

### Cảnh báo học sinh — tiêu chí 2.1 (02/11/2026)

- Mỗi lần yêu cầu chụp danh sách học sinh và thời lượng theo lịch. AI nhận các tên
  hiển thị để đối chiếu lời gọi/tên trong phòng học; không nhận dạng khuôn mặt.
  Học sinh không ghép được danh tính phải được ghi là chưa xác định, không bịa kết quả.
- Báo cáo có từng học sinh, mốc xuất hiện/join `Phần N · MM:SS`, dẫn chứng tham gia,
  dấu hiệu gián đoạn tập trung/tham gia và số học sinh có cảnh báo. Không coi tắt
  camera, nhìn sang chỗ khác hoặc im lặng suy nghĩ là mất tập trung.
- Chỉ tính trễ khi có sự kiện vào lớp rõ ràng và trong cùng phần với mốc bắt đầu
  dạy đã xác định. Server tính độ trễ, trình bày cả phút:giây/phút, thời lượng theo
  lịch, thời lượng thực dạy và tổng video. Không lấy lần đầu phát biểu làm giờ vào.
  Không cộng các đoạn rời để suy ra trễ; không giả định video bắt đầu đúng giờ học.
  Mốc bắt đầu video là 00:00 của từng phần; chưa biết giờ quay thực tế trên đồng hồ.
- Không thấy học sinh trong toàn bộ bản ghi là cảnh báo cần xác nhận vắng,
  không phải kết luận điểm danh. Phải có dẫn chứng cho từng phần; thiếu đoạn hoặc
  không rõ danh tính thì dùng chưa xác định. Không tự cập nhật điểm danh, học phí,
  lương hay chấm điểm học sinh từ báo cáo này.
- Đổi danh sách/tên học sinh hoặc thời lượng sau khi yêu cầu sẽ làm báo cáo cũ
  được đánh dấu cần đối chiếu lại. Không tự chạy lại video khi sửa điểm danh.
- Nội dung hiện trong form nhận xét, tab Nhận xét AI của buổi học và modal riêng
  của giáo viên. Không xuất cảnh báo học sinh lên mô tả/bình luận YouTube hay lịch
  công khai. Báo cáo cũ giữ nguyên; muốn có tiêu chí mới phải Phân tích lại.

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
