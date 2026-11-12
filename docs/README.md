# Tài liệu kỹ thuật FableCut-Studio (`/docs`)

> **Trạng thái hiện tại**: Pipeline và QA đã được cập nhật; test và đồng bộ tài liệu đang được xác minh (`2026-11-12`).
>
> Tài liệu kỹ thuật đã hợp nhất về thư mục này ngày 2026-11-12 (trước đây nằm rải ở gốc repo, `fablecut-bundle/docs/` và `youtube-analyst-niches-forest/design/`).

---

## Danh mục tài liệu

| Tệp | Nội dung |
|---|---|
| [`HUONG-DAN-SU-DUNG.md`](./HUONG-DAN-SU-DUNG.md) | Hướng dẫn vận hành pipeline và cấu trúc các thư mục. |
| [`PIPELINE-QA.md`](./PIPELINE-QA.md) | Kiểm tra pipeline: validate fixture, biên dịch ops, kiểm tra render. Chạy các lệnh từ thư mục `fablecut-bundle/`. |
| [`VIEWER-VIDEO-LIMITATIONS.md`](./VIEWER-VIDEO-LIMITATIONS.md) | Giới hạn quan sát được từ video irrigation hiện có và project rev 41; chỉ là ghi chú chẩn đoán, không chỉnh sửa hoặc render lại tài sản nguồn. |
| [`CHECKLIST.md`](./CHECKLIST.md) | Checklist kiểm tra ban đầu; lưu ý các cảnh báo bảo mật vẫn cần xác minh. |
| [`PROJECT_MODELS.md`](./PROJECT_MODELS.md) | Ghi chú model và trạng thái kiểm chứng pipeline. |
| [`LINKS-DA-XAC-MINH.md`](./LINKS-DA-XAC-MINH.md) | Các liên kết và thông tin repo đã xác minh. |
| [`design/README.md`](./design/README.md) | Danh mục tài liệu thiết kế gốc của công cụ phân tích (6 file `00`–`05`); xem như lịch sử thiết kế, không phải đặc tả hiện hành. |
| [`archive/SHORTS-IMPROVEMENT-PLAN.md`](./archive/SHORTS-IMPROVEMENT-PLAN.md) | **LƯU TRỮ, ĐÃ LỖI THỜI.** Kế hoạch cải tiến tổng thể 4 pha; các hạng mục trong đó phần lớn đã có trong code (xác minh 2026-11-12). Không dùng làm căn cứ triển khai. |
| [`archive/FOUR-PROJECT-DATA-TEMPLATE-ALIGNMENT-PLAN.md`](./archive/FOUR-PROJECT-DATA-TEMPLATE-ALIGNMENT-PLAN.md) | **LƯU TRỮ.** Kế hoạch đồng bộ hợp đồng dữ liệu, template, backend, adapter, FableCut project/media và QA xuyên suốt bốn dự án. |
| [`archive/README.txt`](./archive/README.txt) | **LƯU TRỮ.** Chỉ dẫn đọc tài liệu và bắt đầu vận hành theo bố cục cũ (note bàn giao 2026-11-10, giữ nguyên nội dung). |
| [`00-Huong-dan-OpenCode-9Router-FableCut.pdf`](../fablecut-bundle/docs/00-Huong-dan-OpenCode-9Router-FableCut.pdf) | Tài liệu PDF hướng dẫn OpenCode, 9Router và FableCut (được chuyển nguyên bản). File duy nhất còn ở vị trí cũ vì connector không di dời được file nhị phân; nội dung không đổi. |

---

## Tóm tắt nhanh tiến độ (Snapshot)

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Tách export theo `video_id` & `cleanup_video_temp_files` (`process_video`) | **Xong** | `youtube-analyst-niches-forest` (24/24 pytest pass, 2026-11-12) |
| `cleanup.py` + `cleanup.bat` (dọn lô an toàn) | **Xong** | Bảo vệ `exports/`, `library/`, `projects/`, media đang mở |
| Bộ 6 template `v1.1.0` + `presets/styles.json` (14 styles) | **Xong** | Tại `presets/templates/` và `presets/styles.json` |
| SVG `step-1..3.svg` + chuẩn hóa 21 SFX (`soft_chime.wav`) | **Xong** | Tại `fablecut-data/library/svg/` và `sfx/` |
| Kiểm toán mã nguồn `FableCut`, `fablecut-bundle`, `youtube-analyst-niches-forest` | **Xong** | Đã chốt toàn bộ thông số & bug cần sửa |
| **Pha 1–3**: Schema, preset, adapter và backend đồng bộ | **Đã cập nhật** | Bao gồm validation interchange, export isolation, TTS timing, SFX IDs và template cues |
| **Pha 4**: `qa_check.py` và kiểm thử pipeline | **Đã cập nhật** | Pytest và QA fixtures đã chạy; chưa tạo render mới |

---

## Ràng buộc bất biến khi triển khai

1. **Không sửa code lõi `FableCut`** (`server.js`, `mcp-server.js`, `app.js`, `project-ops.js`, `templates.js`, `delivery.js`, `mask.js`, `audio-fx.js`, `color.js`, v.v.).
2. **Dựng timeline xác định (Deterministic)** qua `schema/input_schema.json` + `presets/` + `adapter/convert.py` (không để LLM tự bịa op JSON hoặc thêm Remotion/Whisper thừa).
3. **Dữ liệu nằm ngoài repo `FableCut`** trong `D:\HOANG HA\Deverlopper Software\fablecut-data\`.
4. **Cảnh báo bảo mật mở ([`CHECKLIST.md`](./CHECKLIST.md))**: `9Router` hiện bind `0.0.0.0` và chưa xác nhận `JWT_SECRET` — giữ cảnh báo trong báo cáo, không tự ý sửa cấu hình bảo mật.
