# Bộ 5 template video — đọc nhanh cho sa

Sa copy thư mục `templates/` vào dự án của mình, đặt ở `presets/templates/`. Coding agent đọc `README-AGENT.md` + `templates/index.json` trước, rồi mới làm video.

## 5 template là gì

| Template | Khi nào dùng |
|---|---|
| hazard-rescue | Ca móng đau, con vật khập khiễng, máy hỏng cần cứu hộ khẩn cấp |
| shock-hook | Có fact / con số gây sốc ở 3 giây đầu |
| how-it-works | Giải thích máy hoạt động theo từng bước |
| satisfying | Quá trình làm việc tự nó đã thỏa mãn, ít chữ |
| before-after | Có sự thay đổi rõ: trước / sau |
| story | Kể chuyện người làm nghề, có vấn đề và bước ngoặt |

Mỗi template khác nhau cả cấu trúc (thứ tự và độ dài các đoạn), chữ, hiệu ứng chuyển cảnh, filter, motion và SFX — không chỉ khác màu.

## Ví dụ

Thư mục `examples/` có cùng 1 clip tưới cây 31,44s nhưng làm theo 5 template khác nhau, để sa so sánh trực quan trước khi chốt.

## Đổi template sau này

Được, có 3 cách (đã ghi chi tiết trong README-AGENT.md):
1. Đổi cho 1 video thôi — template gốc không đổi.
2. Đổi luôn template gốc — sửa file template, tăng version, render thử 1 clip trước.
3. Tạo biến thể mới — copy template cũ sang id mới, ví dụ shock-hook-v2.

Agent chỉ được dùng hiệu ứng có trong danh sách cho phép của template, không tự bịa tên hiệu ứng mới.
# ĐÃ NGỪNG DÙNG LÀM NGUỒN CHUẨN

Registry chuẩn hiện nằm ở `presets/templates/` (phiên bản `1.1.0`). Giữ thư mục này để tương thích lịch sử; không thêm template mới hoặc tra cứu ID template mới tại đây.
