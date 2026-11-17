# Link đã xác minh — chỉ dùng các link này

Ngày kiểm tra: 2026-11-10. Nếu một link không mở được hoặc hiển thị khác mô tả dưới đây, dừng lại và hỏi trước khi clone/cài.

## 1. FableCut — repo cần clone (link trong PDF là đúng)

```
git clone https://github.com/ronak-create/FableCut
```

- Trang repo: https://github.com/ronak-create/FableCut
- Owner đúng: **ronak-create**
- Repo đúng: **FableCut** (viết đúng hoa/thường như vậy)
- Giấy phép: MIT
- Số sao lúc kiểm tra 10/11/2026: khoảng 786 stars, 389 commits, 103 forks
- Dấu hiệu link sai: owner khác (ví dụ `ronak`, `fablecut`, `FableCut-app`...), tên repo khác (`fable-cut`, `Fablecut`, `fablecut-ai`, `FableCut-2`...), repo không có file `mcp-server.js` và `server.js` ở thư mục gốc, hoặc repo yêu cầu nhập key lạ / tải file .exe lạ.
- Nếu clone sai: xóa thư mục vừa clone, không chạy `node server.js` trong đó, clone lại bằng đúng link trên.

## 2. 9Router — cổng LLM

- Trang repo: https://github.com/decolua/9router
- Owner đúng: **decolua**, repo: **9router**
- Chạy local tại: http://localhost:20128/v1 — dashboard: http://localhost:20128/dashboard
- An toàn: dùng bản 0.4.44 trở lên, đặt JWT_SECRET riêng, chỉ bind 127.0.0.1. Xem mục 10 trong PDF.

## 3. OpenCode

- Trang chủ: https://opencode.ai
- Repo: https://github.com/sst/opencode

## 4. Plugin OpenCode ↔ 9Router

- Repo: https://github.com/vheins/opencode-9router
- Tên package trong `opencode.json`: `@vheins/opencode-9router@latest`
- Plugin tự phát hiện model từ `http://localhost:20128`.

## 5. Các link khác trong tài liệu

- OpenFilm (chỉ để tham khảo, không phải repo chính của bộ này): https://openfilm.dev/
- Không có link tải nào khác. Không tải FableCut / 9Router từ link rút gọn, link drive lạ, hay file .exe gửi qua chat.
