Font nghiêng của hero: Lora Medium Italic (Lora-MediumItalic.ttf).
Font được lưu cùng dự án, hỗ trợ tiếng Việt và dùng nét nghiêng thật.
Nguồn: Google Fonts, https://fonts.google.com/specimen/Lora
Giấy phép SIL Open Font License 1.1: xem Lora-OFL.txt.

Font tiêu đề các section của landing page: "SVN-Bebas Neue Pro".

File font KHÔNG nằm trong git. Đặt vào thư mục này, đúng tên:

    SVN-BebasNeuePro.woff2   (ưu tiên, nhẹ nhất)
    SVN-BebasNeuePro.ttf     (dự phòng, có thể đổi tên từ file .ttf gốc của font)

Nếu chỉ có file .otf thì đổi sang .ttf hoặc .woff2 bằng công cụ chuyển đổi font, rồi đặt tên như trên.
Trình duyệt thử lần lượt woff2 rồi ttf, nên chỉ cần có một trong hai.

Nếu máy người xem đã cài sẵn font "SVN-Bebas Neue Pro" thì trình duyệt dùng luôn font đó (local()).
Khi không có file font và máy cũng chưa cài, tiêu đề rơi về sans-serif mặc định, vẫn đọc được tiếng Việt
nhưng không còn dáng chữ Bebas.

Giấy phép: SVN-Bebas Neue Pro không phải font hệ thống. Bạn cần chắc mình được phép dùng trên website
thương mại của trung tâm trước khi đưa file lên server.

Sau khi thêm file: nâng cấp module (-u edu_landing) hoặc xoá cache trình duyệt, rồi tải lại trang.
