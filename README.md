# FableCut Studio

> Bộ công cụ dựng và xuất video ngắn dọc 9:16, kết hợp FableCut Editor, bộ adapter/preset và công cụ phân tích video. Tài liệu vận hành chi tiết bằng tiếng Việt nằm trong [`HUONG-DAN-SU-DUNG.md`](docs/HUONG-DAN-SU-DUNG.md).

## Thành phần

| Thư mục | Vai trò |
| --- | --- |
| [`FableCut/`](FableCut/) | FableCut Editor và engine dựng video. |
| [`fablecut-bundle/`](fablecut-bundle/) | Adapter chuyển kịch bản, schema, preset, ví dụ và script quản lý server. |
| [`youtube-analyst-niches-forest/`](youtube-analyst-niches-forest/) | Công cụ phân tích video và tạo đầu vào cho quy trình dựng. Có môi trường Python riêng. |
| [`fablecut-data/`](fablecut-data/) | Dữ liệu làm việc cục bộ: project, media, thư viện và video xuất. Không đưa dữ liệu runtime vào Git. |

## Yêu cầu

- Windows và PowerShell (các file khởi chạy hiện được cung cấp dưới dạng `.bat`).
- Git.
- Node.js/npm cho FableCut Editor.
- Python cho công cụ phân tích và adapter.
- FFmpeg/ffprobe nếu quy trình xử lý media trên máy chưa có sẵn.

Phiên bản và cách cài phụ thuộc từng thành phần. Xem hướng dẫn tương ứng trong các thư mục, đặc biệt `youtube-analyst-niches-forest/README.md` và `FableCut/README.md`.

## Chạy FableCut

1. Mở PowerShell tại `fablecut-bundle/`.
2. Khởi động server:

   ```powershell
   .\server.bat start
   ```

3. Mở `http://localhost:7777` trong trình duyệt.
4. Khi hoàn tất, dừng server bằng:

   ```powershell
   .\server.bat stop
   ```

Có thể chạy `server.bat` không có tham số để xem menu thao tác. Server dùng dữ liệu làm việc trong `fablecut-data/`.

## Quy trình tổng quát

1. Phân tích video và chuẩn bị kịch bản/voiceover bằng `youtube-analyst-niches-forest/`, hoặc dùng nguyên liệu có sẵn.
2. Đặt media đầu vào theo `video_id` trong `fablecut-data/media/<video_id>/`.
3. Dùng adapter trong `fablecut-bundle/adapter/` để kiểm tra/chuyển kịch bản, hoặc dựng trực tiếp trong FableCut Editor.
4. Xem trước và xuất video; đầu ra được lưu trong `fablecut-data/exports/`.

Chi tiết về định dạng file, cấu hình, MCP và các bước thao tác nằm trong [`HUONG-DAN-SU-DUNG.md`](docs/HUONG-DAN-SU-DUNG.md) và tài liệu dưới [`docs/`](docs/README.md).

## Dữ liệu và bảo mật

- `.gitignore` ở thư mục gốc loại trừ file môi trường, cache, môi trường ảo, metadata Git lồng nhau và dữ liệu media/runtime cục bộ.
- Không commit `.env`, khóa API, dữ liệu cá nhân, media có bản quyền hoặc file xuất lớn.
- `.env.example` chỉ là mẫu cấu hình; sao chép thành `.env` và điền giá trị riêng trên máy khi cần.
- Git ignore không gỡ file đã được commit trước đó khỏi lịch sử. Kiểm tra `git status` trước khi commit.

## Kiểm tra trạng thái Git

```powershell
git status
git remote -v
git branch --show-current
```
