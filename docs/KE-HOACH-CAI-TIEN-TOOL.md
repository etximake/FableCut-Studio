# Kế hoạch cải tiến tool: từ backend đến frontend

## Mục tiêu

Cải thiện pipeline tạo video về **nông nghiệp, máy móc nông nghiệp và đào mỏ** để nội dung đáng tin, ít lặp, có nhịp kể phù hợp mục đích xem; không mặc định giật gân, hài hước hay “thỏa mãn”.

Kế hoạch gồm sáu hạng mục triển khai tuần tự. Đây là tài liệu định hướng, chưa phải thay đổi mã nguồn.

## Nguyên tắc kiến trúc

Giữ backend theo luồng:

**API routes → use cases/services → domain models & validators → adapters (LLM, TTS, database, exporter)**

- `routes.py` chỉ nhận request, gọi use case và trả response; không chứa logic biên kịch hoặc điều phối pipeline.
- Dữ liệu đầu vào/đầu ra được định nghĩa trong `src/models/schemas.py`, kiểm tra rõ trước khi lưu hoặc xuất.
- Vision, biên kịch, TTS và export giao tiếp qua giao diện rõ ràng; thay model hoặc nhà cung cấp không làm thay đổi logic nghiệp vụ.
- Frontend tiếp tục dùng HTML/CSS/JavaScript hiện tại; tách JavaScript thành các module theo chức năng thay vì viết lại toàn bộ sang framework.
- Không sửa lõi trong `FableCut/`; không ghi đè dữ liệu project, media hoặc export hiện có.

---

## 1. Cho người dùng chọn mục đích video trước khi phân tích

### Vấn đề

Template hiện chủ yếu được chọn theo skill hoặc một số từ khóa trong mô tả hình ảnh. Hệ thống có thể chọn sai kiểu kể chuyện cho clip.

### Backend

- Bổ sung lựa chọn có cấu trúc cho **chủ đề**: nông nghiệp cây trồng, máy móc nông nghiệp, đào mỏ hoặc chủ đề khác.
- Bổ sung **mục đích video**: giải thích cơ chế, hướng dẫn/thực hành, cho xem quy trình vận hành, kết quả trước–sau, hoặc sự cố và cách xử lý.
- Chọn template dựa trên các trường này cùng timeline, thay vì dò từ khóa đơn lẻ.
- Trả về template được chọn và lý do, ví dụ: “chọn `satisfying` vì quy trình vận hành là trọng tâm và không có thông tin kỹ thuật cần giải thích”.

### Frontend

- Thêm lựa chọn chủ đề và mục đích trong phần cấu hình đầu vào.
- Hiển thị template được đề xuất, lý do chọn và cho phép người dùng đổi trước khi tạo lời bình.

### Tiêu chí hoàn thành

- Cùng một video có thể tạo ra kiểu nội dung khác nhau khi mục đích xem khác nhau.
- Không chọn `shock-hook` chỉ vì clip có chi tiết lạ nếu người dùng muốn giọng giải thích thực dụng.

## 2. Tăng độ tin cậy của phân tích hình ảnh và âm thanh

### Vấn đề

Contact sheet 3×3 giúp tiết kiệm chi phí nhưng có thể bỏ lỡ thao tác ở giữa clip. Mô tả tổng quát cũng dễ bị biến thành lời khẳng định không có bằng chứng.

### Backend

- Chuẩn hóa kết quả Vision thành sự kiện có mốc thời gian và nhãn bằng chứng:
  - `observed`: thấy trực tiếp trong hình;
  - `heard`: có trong âm thanh hoặc lời nói;
  - `inferred`: suy luận, cần thận trọng;
  - `unknown`: không đủ dữ kiện.
- Gắn độ tin cậy cho từng sự kiện; không để mô hình tự nâng độ tin cậy hoặc bổ sung chi tiết không quan sát được.
- Chỉ yêu cầu phân tích thêm khung hình khi cần xác minh một sự kiện quan trọng; tránh gửi thêm dữ liệu tốn kém cho mọi clip.
- Giữ transcript/audio hint tách biệt với quan sát hình ảnh để tránh nhầm lời người nói với sự thật đã xác minh.

### Frontend

- Hiển thị timeline kèm nhãn “đã thấy”, “từ âm thanh”, “suy luận”, “chưa rõ”.
- Cho người dùng sửa hoặc xác nhận mô tả trước khi tạo lời bình.

### Tiêu chí hoàn thành

- Phát biểu về năng suất, khoảng cách, nguyên nhân, kỹ thuật hoặc lợi ích không được đưa vào như sự thật nếu không có nguồn hỗ trợ.
- Người dùng phân biệt được câu nào do AI quan sát và câu nào là suy đoán.

## 3. Tách logic biên kịch khỏi lựa chọn template

### Vấn đề

Template và skill cùng tác động đến lời bình; nếu prompt không đủ rõ, kết quả có thể chỉ đổi tên beat nhưng vẫn lặp khuôn hoặc suy diễn.

### Backend

Chia quy trình tạo nội dung thành ba phần có hợp đồng dữ liệu riêng:

1. **Góc kể:** chọn luận điểm và thông tin chính dựa trên mục đích video.
2. **Lời bình:** tạo câu thoại dựa trên sự kiện đã xác minh.
3. **Định dạng trình bày:** gán lời bình vào beat của template đã chọn.

Quy định theo chủ đề:

- Nông nghiệp: kinh nghiệm, thao tác, điều kiện hoặc kết quả nhìn thấy; không tự bịa lời khuyên canh tác.
- Máy móc nông nghiệp: thao tác, bộ phận và tác dụng chỉ khi có bằng chứng.
- Đào mỏ: quy trình, thiết bị, vật liệu hoặc quy mô chỉ khi có thể xác nhận.

Thêm kiểm tra sau sinh để phát hiện câu vượt quá bằng chứng, beat rỗng, hook chung chung, câu kết lặp và nội dung không phù hợp mục đích. Chỉ tự động viết lại khi lỗi xác định được; nếu không chắc, đánh dấu cần người dùng duyệt.

### Frontend

- Cho xem lời bình cùng nguồn bằng chứng liên quan.
- Đánh dấu câu cần xem lại thay vì âm thầm sửa hoặc loại bỏ.

### Tiêu chí hoàn thành

- Lời bình mô tả cụ thể clip, không mặc định câu mở kiểu “Bạn có biết…” hay kết luận quảng cáo chung chung.
- Hệ thống cảnh báo claim thiếu căn cứ thay vì trình bày như dữ kiện.

## 4. Làm template và compiler khớp nhau về timeline, nội dung và hiệu ứng

### Vấn đề

Template có cấu trúc, thời lượng và hướng dẫn trình bày, nhưng adapter không tự đảm bảo mọi hướng dẫn được chuyển thành timeline đúng. Clip ngắn cũng có thể dùng template thiết kế cho clip dài.

### Backend

- Tách rõ **content data** (lời bình, bằng chứng, mốc thời gian) khỏi **presentation data** (chữ, chuyển cảnh, màu sắc, SFX).
- Chỉ cho compiler nhận template đã xác thực; lỗi template hoặc beat không tương thích phải báo rõ, không âm thầm dùng mặc định.
- Co giãn thời lượng beat theo thời lượng clip nhưng không làm lời bình vượt thời gian hoặc cắt câu.
- Kiểm tra trước khi xuất:
  - timeline không có khoảng trống hoặc chồng lấn ngoài ý muốn;
  - tổng thời lượng không vượt clip;
  - mọi beat đều hợp lệ;
  - SFX, SVG và hiệu ứng được phép tồn tại;
  - slow motion không làm lệch tiếng, phụ đề và hình.
- Bổ sung chế độ dựng tối giản cho video vận hành máy: giữ âm thanh hiện trường, hạn chế chữ và hiệu ứng khi phù hợp.

### Frontend

- Hiển thị template và nhịp beat dự kiến trước khi xuất.
- Cảnh báo khi clip ngắn hơn thời lượng khuyến nghị hoặc template có hiệu ứng không phù hợp với nội dung.

### Tiêu chí hoàn thành

- Không còn đoạn voiceover vượt thời lượng clip hoặc template áp máy móc vào video quá ngắn.
- Tên beat trong kịch bản được ánh xạ rõ ràng sang cấu hình template mà compiler thực sự áp dụng.

## 5. Biến giao diện thành quy trình biên tập có thể kiểm soát

### Vấn đề

Giao diện hiện có khu vực cấu hình, kiểm tra timeline và chỉnh sửa lời bình, nhưng luồng duyệt cần rõ hơn để người dùng quyết định trước khi tạo TTS và export.

### Frontend

- Chia quy trình thành các bước có trạng thái: **Nguồn video → Kiểm tra phân tích → Chọn hướng kể/template → Duyệt lời bình → Nghe thử → Xuất**.
- Tách JavaScript thành module theo trách nhiệm: API client, state/workflow, video input, timeline inspector, script editor, TTS preview và export.
- Giữ HTML/CSS hiện có; loại dần xử lý nghiệp vụ khỏi global functions và inline handlers.
- Thêm trạng thái tải, lỗi, thử lại và cảnh báo dữ liệu chưa lưu nhất quán cho từng bước.
- Hỗ trợ xem bản dịch tiếng Việt bên cạnh lời bình tiếng Anh, phát audio theo từng đoạn và sửa nội dung trước khi tạo bản cuối.

### Backend

- Tách endpoint theo hành động nghiệp vụ rõ ràng: phân tích, tạo lời bình, tạo lại một phần, synthesize, export.
- Bảo đảm lỗi TTS không làm mất kịch bản; lỗi export không làm mất kết quả phân tích.
- Lưu trạng thái bản nháp và phiên bản kịch bản theo cơ chế hiện có trước khi mở rộng tính năng.

### Tiêu chí hoàn thành

- Người dùng có thể xem và chỉnh lời bình trước khi xuất, biết bước nào thất bại và thử lại đúng bước đó.
- Frontend không phải biết chi tiết provider/model để điều khiển pipeline.

## 6. Thiết lập QA tự động và đánh giá bằng bản render thật

### Vấn đề

Test hiện tại xác nhận API hoặc file được tạo, nhưng chưa đo chất lượng kịch bản, mức lặp và độ khớp giữa render với timeline.

### Backend

- Xây bộ dữ liệu kiểm thử đại diện cho ba chủ đề và các mục đích video khác nhau.
- Thêm test cho:
  - phát biểu không có bằng chứng;
  - lựa chọn template;
  - timeline ngắn/dài, beat thiếu hoặc lệch;
  - voiceover bị cắt;
  - subtitle không khớp thời gian;
  - template hoặc asset không hợp lệ.
- Ghi metadata phục vụ đánh giá: chủ đề, mục đích, template, phiên bản prompt/model, cảnh báo validation. Không lưu bí mật hoặc thêm dữ liệu cá nhân không cần thiết.

### Frontend và quy trình QA

- Hiển thị cảnh báo kiểm định trước khi export.
- Với mỗi thay đổi template/compiler, render một clip mẫu và kiểm tra hình thực tế, vùng an toàn chữ, nhịp chuyển cảnh, tiếng hiện trường, voiceover và phụ đề.
- Đánh giá hook, luận điểm và câu kết giữa các video gần nhau để phát hiện lặp khuôn.

### Tiêu chí hoàn thành

- Test cấu trúc và test render đều chạy trước khi đánh dấu template đã xác minh.
- Không coi “JSON hợp lệ” hoặc “file MP4 tồn tại” là đủ bằng chứng chất lượng.

## Thứ tự triển khai đề xuất

**1 → 2 → 3 → 4 → 5 → 6.** Bắt đầu bằng việc người dùng xác định đúng mục đích video; sau đó cải thiện dữ liệu quan sát, biên kịch và template. Khi kết quả backend ổn định, hoàn thiện luồng giao diện rồi khóa chất lượng bằng QA và render thực tế.

Kế hoạch ưu tiên **độ tin cậy, khả năng kiểm soát và kiến trúc rõ ràng** trước hiệu ứng hoặc tự động hóa thêm.
