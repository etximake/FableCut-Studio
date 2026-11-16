# Kiến trúc phối hợp ChatGPT Web và OpenCode cho một dự án

## 1. Kết luận

Nên sử dụng ChatGPT Web kết hợp với OpenCode, nhưng phải phân chia rõ
trách nhiệm. Không cần đưa toàn bộ quá trình coding lên ChatGPT Web.

Mô hình đề xuất:

-   **ChatGPT Project:** Bộ não thiết kế, quản lý tri thức và kiểm soát
    các quyết định kỹ thuật.
-   **OpenCode:** Môi trường thực thi, triển khai mã nguồn và kiểm thử.
-   **Cohere North Mini Code qua xKiro Free:** Model coding duy nhất
    theo lựa chọn hiện tại, dùng cho Main Developer và các Subagent.
-   **Người dùng:** Người phê duyệt cuối cùng đối với các thay đổi quan
    trọng về kiến trúc, phạm vi, bảo mật và dữ liệu.

## 2. Phân chia vai trò

### 2.1. ChatGPT Web --- Technical Architect

ChatGPT Web đảm nhiệm:

-   Phân tích yêu cầu và làm rõ phạm vi.
-   Thiết kế kiến trúc hệ thống.
-   Xây dựng và duy trì tài liệu kỹ thuật chuẩn.
-   Đánh giá các đề xuất thay đổi thiết kế từ OpenCode.
-   Phân tích các lỗi có dấu hiệu xuất phát từ thiết kế hoặc kiến trúc.
-   Đề xuất phương án và nêu rõ tác động, rủi ro, điều kiện kiểm thử.
-   Hỗ trợ đánh giá kết quả review, testing và nghiệm thu.

ChatGPT Web không mặc định có quyền truy cập trực tiếp vào mã nguồn,
Git, môi trường chạy hoặc trạng thái thực tế trên máy người dùng. Những
dữ liệu này phải được cung cấp qua tài liệu, log, diff hoặc một tích hợp
được thiết lập riêng.

### 2.2. OpenCode --- Implementation Environment

OpenCode đảm nhiệm việc làm việc trực tiếp với mã nguồn và môi trường dự
án:

  -----------------------------------------------------------------------
  Agent                               Trách nhiệm
  ----------------------------------- -----------------------------------
  Main Developer                      Nhận yêu cầu, phân rã công việc,
                                      điều phối Subagent và tổng hợp kết
                                      quả

  Coder                               Triển khai hoặc sửa mã nguồn theo
                                      thiết kế đã duyệt

  Reviewer                            Đánh giá yêu cầu, thiết kế và diff;
                                      không tự ý sửa code hoặc thay đổi
                                      kiến trúc

  Tester                              Xây dựng/chạy kiểm thử và báo cáo
                                      kết quả

  Researcher                          Nghiên cứu thư viện, công nghệ hoặc
                                      vấn đề kỹ thuật khi cần
  -----------------------------------------------------------------------

Không nhất thiết phải tạo tất cả Agent ngay từ đầu. Có thể bắt đầu với
Main Developer, Coder và Reviewer; chỉ tách Tester hoặc Researcher khi
khối lượng công việc thực tế cần đến.

Các Agent sử dụng Cohere North Mini Code thông qua xKiro Free theo cấu
hình đã chọn. Model ID, giới hạn context, quota, khả năng gọi tool và
schema cấu hình phải được xác minh trên môi trường thực tế trước khi
triển khai.

## 3. Phân công công việc

  -----------------------------------------------------------------------
  Công việc               ChatGPT Web             OpenCode
  ----------------------- ----------------------- -----------------------
  Phân tích yêu cầu       Chủ trì                 Hỗ trợ khảo sát

  Thiết kế kiến trúc      Chủ trì                 Phản biện tính khả thi

  Viết tài liệu kỹ thuật  Chủ trì                 Cập nhật theo triển
                                                  khai được duyệt

  Khảo sát mã nguồn hiện  Phân tích dữ liệu được  Chủ trì
  tại                     cung cấp                

  Coding                  Không bắt buộc          Chủ trì

  Phân tích lỗi code      Hỗ trợ khi cần          Chủ trì

  Phát hiện và báo cáo    Đánh giá, quyết định    Phát hiện, thu thập
  lỗi thiết kế            phương án               bằng chứng

  Review code             Đánh giá độc lập khi    Chủ trì
                          cần                     

  Kiểm thử                Phân tích kết quả và    Chủ trì thực thi
                          tiêu chí                

  Phê duyệt thay đổi kiến Đề xuất để người dùng   Không tự phê duyệt
  trúc                    quyết định              
  -----------------------------------------------------------------------

## 4. Tổ chức ChatGPT Project

Nên tạo một ChatGPT Project riêng cho từng dự án. Ví dụ:
`Physics Simulation Studio`.

Cấu trúc tài liệu tham khảo:

``` text
Project/
├── 01-Project-Overview.md
├── 02-Requirements-Specification.md
├── 03-System-Architecture.md
├── 04-Technical-Design.md
├── 05-Architecture-Decision-Records/
├── 06-Change-Requests/
├── 07-OpenCode-Implementation-Reports/
└── 08-Testing-and-Acceptance/
```

Ý nghĩa:

-   `Project Overview`: Mục tiêu, phạm vi, đối tượng sử dụng và các giới
    hạn.
-   `Requirements Specification`: Yêu cầu chức năng và phi chức năng,
    tiêu chí nghiệm thu.
-   `System Architecture`: Kiến trúc tổng thể và ranh giới các thành
    phần.
-   `Technical Design`: Thiết kế chi tiết, giao diện, dữ liệu và luồng
    xử lý.
-   `Architecture Decision Records`: Các quyết định kiến trúc đã được
    phê duyệt và lý do.
-   `Change Requests`: Các đề xuất thay đổi đang chờ xem xét hoặc đã
    được quyết định.
-   `Implementation Reports`: Báo cáo triển khai từ OpenCode.
-   `Testing and Acceptance`: Kế hoạch, kết quả kiểm thử và trạng thái
    nghiệm thu.

Đây là cấu trúc đề xuất; có thể điều chỉnh theo quy mô dự án. Cần duy
trì một bản tài liệu chuẩn có phiên bản, ngày cập nhật và trạng thái phê
duyệt để tránh các bản tài liệu mâu thuẫn.

## 5. Quy trình phối hợp

### 5.1. Khởi tạo dự án

1.  Làm rõ yêu cầu và phạm vi trên ChatGPT Project.
2.  Xây dựng tài liệu yêu cầu, kiến trúc và thiết kế kỹ thuật.
3.  Ghi lại các quyết định kiến trúc quan trọng trong ADR.
4.  Người dùng xem xét và phê duyệt bộ thiết kế ban đầu.
5.  Chuyển bộ tài liệu đã duyệt cho OpenCode.
6.  OpenCode khảo sát mã nguồn, môi trường và lập kế hoạch triển khai.
7.  Người dùng xem xét kế hoạch trước khi cho phép các thay đổi có rủi
    ro.

### 5.2. Triển khai bình thường

1.  Người dùng giao nhiệm vụ cho Main Developer.
2.  Main Developer phân rã nhiệm vụ theo thiết kế đã duyệt.
3.  Coder triển khai.
4.  Reviewer đánh giá diff và mức độ đáp ứng yêu cầu.
5.  Tester chạy các kiểm thử phù hợp.
6.  Main Developer tổng hợp kết quả và báo cáo.
7.  OpenCode cập nhật tài liệu triển khai, test report và trạng thái
    công việc.
8.  Các thay đổi được quản lý bằng Git theo quy trình của dự án.

### 5.3. Khi phát hiện lỗi thiết kế

Ví dụ: Coder phát hiện thiết kế ban đầu không đáp ứng được một tình
huống nghiệp vụ hoặc gây ra vấn đề về hiệu năng.

Quy trình:

1.  Coder dừng phần triển khai bị ảnh hưởng; không tự ý mở rộng phạm vi
    sửa đổi.
2.  OpenCode thu thập bằng chứng: log, bước tái hiện, file và vị trí
    code liên quan, kết quả test.
3.  Main Developer lập Architecture Change Request (ACR).
4.  Người dùng chuyển ACR và các tài liệu liên quan sang ChatGPT
    Project.
5.  ChatGPT phân tích nguyên nhân, đề xuất các phương án và đánh giá tác
    động.
6.  Người dùng quyết định phương án.
7.  Cập nhật tài liệu thiết kế và ADR nếu cần.
8.  Chuyển thiết kế đã duyệt về OpenCode.
9.  OpenCode cập nhật kế hoạch, triển khai và chạy lại kiểm thử.

OpenCode không được tự coi đề xuất thay đổi thiết kế là quyết định đã
được phê duyệt.

## 6. Mẫu Architecture Change Request (ACR)

``` markdown
# Architecture Change Request

- ID:
- Ngày:
- Dự án:
- Người đề xuất:
- Trạng thái: Draft / Under Review / Approved / Rejected

## 1. Vấn đề
Mô tả vấn đề phát hiện được.

## 2. Bằng chứng
- Log:
- File/vị trí code:
- Bước tái hiện:
- Kết quả kiểm thử:
- Hành vi thực tế:

## 3. Thiết kế hiện tại
Mô tả thành phần hoặc quyết định đang gây ra vấn đề.

## 4. Nguyên nhân
Phân biệt nguyên nhân đã xác minh và giả thuyết.

## 5. Phương án đề xuất
Nêu các phương án khả thi, ưu/nhược điểm và phương án khuyến nghị.

## 6. Tác động
- API:
- Database:
- Bảo mật:
- Hiệu năng:
- Tương thích ngược:
- Phạm vi và tiến độ:

## 7. Kiểm thử cần bổ sung
Nêu các tiêu chí và trường hợp kiểm thử.

## 8. Khôi phục
Cách quay lại trạng thái trước thay đổi.

## 9. Quyết định
- Người phê duyệt:
- Kết luận:
- Ngày phê duyệt:
```

## 7. Nguyên tắc quản lý tài liệu và trạng thái

-   Tài liệu đã được duyệt là căn cứ triển khai; bản nháp và đề xuất
    không được coi là quyết định.
-   Mỗi thay đổi quan trọng cần có lịch sử, lý do và người phê duyệt.
-   OpenCode phải báo cáo khi phát hiện tài liệu không khớp với mã
    nguồn.
-   Không tự động ghi đè tài liệu thiết kế chuẩn bằng nội dung do Agent
    tạo ra.
-   Báo cáo phải phân biệt rõ nội dung đã kiểm thử, chưa kiểm thử và
    chưa xác minh.
-   Git là nơi quản lý lịch sử mã nguồn; tài liệu chuẩn cũng nên được
    quản lý phiên bản trong repository nếu phù hợp với chính sách dự án.
-   Không đưa API key, token, mật khẩu, dữ liệu cá nhân hoặc thông tin
    nhạy cảm vào tài liệu gửi giữa các môi trường.

## 8. Giới hạn và rủi ro cần kiểm soát

1.  **Không tự động đồng bộ:** ChatGPT Project không mặc định đồng bộ
    thư mục mã nguồn, Git hay báo cáo từ OpenCode. Cần chuyển tài liệu
    và kết quả thủ công hoặc xây dựng tích hợp riêng.
2.  **Sai khác phiên bản tài liệu:** Nếu ChatGPT và OpenCode dùng các
    bản tài liệu khác nhau, có thể phát sinh triển khai sai thiết kế.
    Cần ghi phiên bản hoặc commit tham chiếu trong mỗi lần bàn giao.
3.  **Giới hạn model:** Agent workflow không loại bỏ giới hạn năng lực
    của model. Cần kiểm thử chất lượng model trên các nhiệm vụ đại diện.
4.  **Context và chi phí token:** Subagent giúp tách ngữ cảnh và nhiệm
    vụ nhưng có thể làm tổng lượng token tăng do nhiều lượt gọi và dữ
    liệu lặp lại.
5.  **Quyền Agent:** Reviewer nên có quyền tối thiểu. Cần kiểm tra cả
    quyền sửa file lẫn quyền thực thi lệnh có thể gây thay đổi dữ liệu.
6.  **Quyết định kiến trúc:** Những thay đổi ảnh hưởng API, database,
    xác thực, bảo mật, công nghệ nền tảng, phạm vi hoặc yêu cầu hiệu
    năng cần được phê duyệt trước.

## 9. Lộ trình triển khai đề xuất

### Giai đoạn 1 --- Chuẩn hóa ChatGPT Project

-   Tạo Project riêng cho dự án.
-   Đưa tài liệu yêu cầu và thiết kế chuẩn vào Project.
-   Thiết lập nguyên tắc phân biệt quyết định đã duyệt, đề xuất, giả
    định và nội dung chưa xác minh.
-   Chốt quy trình ACR và ADR.

### Giai đoạn 2 --- Thiết lập OpenCode

-   Đưa tài liệu đã duyệt vào repository.
-   Khảo sát phiên bản OpenCode và cấu hình xKiro hiện tại.
-   Xác minh model ID, context window, quota và khả năng gọi tool.
-   Thiết lập Main Developer, Coder và Reviewer trước.
-   Bổ sung Tester hoặc Researcher khi có nhu cầu.
-   Thiết lập quyền tối thiểu và sao lưu cấu hình trước khi thay đổi.

### Giai đoạn 3 --- Kiểm thử quy trình phối hợp

Thực hiện một nhiệm vụ nhỏ có thể kiểm soát:

1.  Giao Main Developer một yêu cầu coding.
2.  Kiểm tra việc phân rã và giao nhiệm vụ.
3.  Kiểm tra Coder triển khai.
4.  Kiểm tra Reviewer đánh giá độc lập.
5.  Kiểm tra Tester chạy test.
6.  Tạo một lỗi code có kiểm soát để kiểm tra vòng sửa lỗi.
7.  Mô phỏng một vấn đề thiết kế để kiểm tra quy trình ACR.
8.  Xác nhận tài liệu được cập nhật đúng sau khi có quyết định.

Chỉ nghiệm thu các tiêu chí có bằng chứng thực tế. Không đánh dấu PASS
nếu chưa chạy hoặc chưa quan sát được kết quả.

## 10. Kết luận kiến trúc

  -----------------------------------------------------------------------
  Thành phần                          Vai trò chính
  ----------------------------------- -----------------------------------
  ChatGPT Project                     Thiết kế, quản lý tri thức, đánh
                                      giá và kiểm soát quyết định

  OpenCode                            Khảo sát, coding, review, testing
                                      và báo cáo

  Cohere North Mini Code qua xKiro    Model thực thi các nhiệm vụ trong
                                      OpenCode

  Người dùng                          Phê duyệt cuối cùng và kiểm soát
                                      phạm vi
  -----------------------------------------------------------------------

Nên thiết lập ChatGPT Project và chuẩn hóa tài liệu trước, sau đó mới
cấu hình OpenCode. Cách làm này giúp hai môi trường cùng dựa trên một bộ
tài liệu chuẩn, giảm nguy cơ OpenCode triển khai theo thiết kế khác với
thiết kế đang được quản lý.

**Nguyên tắc cốt lõi:** ChatGPT Web định hướng và kiểm soát quyết định;
OpenCode thực thi và cung cấp bằng chứng; người dùng phê duyệt các thay
đổi quan trọng.
