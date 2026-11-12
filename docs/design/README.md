# BỘ TÀI LIỆU THIẾT KẾ: AI VIDEO COMMENTARY & CAPCUT ENGINE

> **Tài liệu thiết kế gốc (lịch sử).** Bộ thiết kế này được viết trước khi triển khai; code hiện tại có thể đã đi xa hơn thiết kế này. Dùng để hiểu kiến trúc ban đầu, không dùng làm đặc tả hiện hành.

Hệ thống tự động hóa thông minh tiếp nhận **1 video ngắn bất kỳ (30s – 60s, điển hình 40s – 50s)** không cần phụ đề, sử dụng công nghệ thị giác tiết kiệm token (Smart Contact Sheet) kết hợp bộ lọc âm thanh đứt đoạn (Audio Truncation Guard), phân tích diễn biến và tự động biên soạn **Lời bình (Voiceover) cuốn hút đa phong cách theo Skill** xuất thẳng sang định dạng **CapCut Interchange JSON**.

---

## 📑 Danh mục tài liệu thiết kế

| STT | Tài liệu | Mô tả chi tiết |
| :--- | :--- | :--- |
| **00** | [00_overview_and_architecture.md](./00_overview_and_architecture.md) | **Tổng quan kiến trúc & Luồng dữ liệu:** Nguyên lý cốt lõi, mô hình Decoupled Two-Stage, chiến lược tiết kiệm 95% token và nguyên tắc "Visual Truth First". |
| **01** | [01_local_video_preprocessor.md](./01_local_video_preprocessor.md) | **Module Tiền xử lý Video Cục bộ (FFmpeg):** Trích xuất lưới ảnh 3x3 in sẵn Timestamp badge, bóc tách âm thanh, VAD filter và xử lý câu thoại đứt đoạn. |
| **02** | [02_two_stage_commentary_engine.md](./02_two_stage_commentary_engine.md) | **Lõi Phân tích 2 Chặng:** Chặng 1 (Vision Action Extractor) bóc tách sự thật khách quan $\rightarrow$ Chặng 2 (Commentary Scriptwriter) viết lời bình. |
| **03** | [03_skills_registry_and_prompts.md](./03_skills_registry_and_prompts.md) | **Hệ thống Skill Biên kịch:** Bộ sưu tập Persona chuẩn OpenCode (Curiosity Explainer, Storyteller, Satisfying, Witty), quy tắc WPM (130-150 từ/phút), Fact-Anchoring. |
| **04** | [04_capcut_interchange_and_api.md](./04_capcut_interchange_and_api.md) | **Đặc tả API & CapCut JSON Schema v3:** REST Endpoints nhận video, cấu trúc JSON tích hợp Voiceover, Text Overlay, SFX Cues và Visual Hints. |
| **05** | [05_ui_ux_commentary_studio.md](./05_ui_ux_commentary_studio.md) | **Thiết kế Giao diện Studio UI/UX:** Studio 3 cột trực quan Dark Mode, trình nghe thử SFX thật, tương tác biên tập kịch bản và xuất CapCut v3. |

---

## 🎯 4 Nguyên tắc thiết kế bất biến (Core Invariant Principles)

1. **Visual Truth First (Hình ảnh là Chân lý số 1):** Hình ảnh trong video là sự thật diễn biến tối thượng. Âm thanh bóc tách chỉ là gợi ý tham khảo (Hint). Nếu âm thanh bị nhiễu, đứt câu hoặc nói nhảm, hệ thống dựa 100% vào hình ảnh để viết lời bình.
2. **Token Efficiency by Design (Tiết kiệm 95% Token):** Không gửi video thô (tốn 15.000 tokens) hay hàng chục ảnh rời (tốn 40.000 tokens). Toàn bộ video được cô đọng thành **1 bức ảnh lưới Contact Sheet 3x3** có in mốc giây rõ ràng, chỉ tiêu tốn ~1.000 tokens.
3. **Decoupled Two-Stage Execution (Tách rời 2 chặng):** Chặng 1 (Đọc thị giác) chạy 1 lần duy nhất $\rightarrow$ sinh Nhật ký hành động. Chặng 2 (Viết lời bình) có thể chạy nhiều lần với nhiều Skill khác nhau với chi phí cực rẻ (~400 text tokens).
4. **Fact-Anchored Storytelling (Bảo toàn sự thật khoa học/kỹ thuật):** Lời bình có thể linh hoạt về giọng điệu, nhịp điệu và câu hook giật gân, nhưng không được bịa đặt nguyên lý, số liệu hay hiện tượng sai lệch so với những gì diễn ra trong video gốc.
