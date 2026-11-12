# AI VIDEO COMMENTARY & CAPCUT ENGINE

> **Hệ thống AI tự động đọc video ngắn (30s – 60s), phân tích chuỗi diễn biến thị giác qua Contact Sheet 3x3 và biên soạn Lời bình (Voiceover) cuốn hút theo Skill, xuất thẳng sang file CapCut Interchange JSON & SRT.**

---

## 🌟 TÍNH NĂNG ĐỘT PHÁ

1. **Không cần phụ đề đầu vào:** Chỉ cần nạp 1 file video (MP4) hoặc URL YouTube Shorts / TikTok.
2. **Tiết kiệm 95% Token (Smart Contact Sheet):**
   - Thay vì gửi cả video (15.000 tokens) hay hàng chục ảnh rời (40.000 tokens), FFmpeg trích xuất **9 khung hình then chốt** in sẵn mốc thời gian và ghép thành **1 bức ảnh lưới 3x3 duy nhất** (~1.000 tokens).
3. **Bộ lọc chống câu thoại bị cắt cụt (Audio Truncation Guard):**
   - Khi cắt 1 clip từ video dài, âm thanh thường bị đứt câu hoặc lẫn tạp âm. Hệ thống sử dụng VAD + bộ lọc dải tần để nhận diện câu cụt, ưu tiên hình ảnh làm chân lý số 1 (`Visual Truth First`).
4. **Kiến trúc Tách rời 2 Chặng (Decoupled Two-Stage):**
   - **Chặng 1 (Vision Action Extractor):** Đọc ảnh 1 lần duy nhất $\rightarrow$ sinh "Nhật ký hành động theo mốc giây thực" và lưu vào SQLite.
   - **Chặng 2 (Commentary Scriptwriter):** Viết lời bình theo Persona biên kịch với chi phí cực rẻ (~400 text tokens). Khi muốn đổi giọng điệu (Khoa học $\leftrightarrow$ Hài hước), hệ thống chỉ chạy lại Chặng 2 mà không đọc lại ảnh.
5. **Kho Persona biên kịch chuẩn OpenCode (Skills Registry):**
   - `curiosity-explainer`: Giải mã hiện tượng, câu hỏi tò mò, tạo khoảnh khắc *Aha!*.
   - `suspense-storyteller`: Hồi hộp, kịch tính, nhịp thở điện ảnh.
   - `satisfying-narrator`: Êm dịu, tôn vinh sự tỉ mỉ, thư giãn giác quan (phục chế, mộc, ASMR).
   - `witty-commentator`: Hài hước, đánh lạc hướng và bẻ lái bất ngờ (Plot Twist).
6. **Đầu ra chuẩn CapCut Interchange JSON v3 & Phụ đề SRT:**
   - Đồng bộ 3 lớp: `voiceover` + `text_overlay` (3-5 từ) + `sfx_cue` (Whoosh, Sub Boom, Ding...).

---

## 🏛️ TÀI LIỆU THIẾT KẾ CHI TIẾT

Toàn bộ đặc tả kỹ thuật và kiến trúc được lưu trữ trong thư mục [`docs/design/`](../docs/design/):
- [`docs/design/README.md`](../docs/design/README.md): Danh mục tài liệu thiết kế.
- [`docs/design/00_overview_and_architecture.md`](../docs/design/00_overview_and_architecture.md): Tổng quan kiến trúc & luồng dữ liệu.
- [`docs/design/01_local_video_preprocessor.md`](../docs/design/01_local_video_preprocessor.md): Module tiền xử lý FFmpeg & Whisper.
- [`docs/design/02_two_stage_commentary_engine.md`](../docs/design/02_two_stage_commentary_engine.md): Lõi phân tích thị giác & biên kịch 2 chặng.
- [`docs/design/03_skills_registry_and_prompts.md`](../docs/design/03_skills_registry_and_prompts.md): Đặc tả hệ thống Skill biên kịch.
- [`docs/design/04_capcut_interchange_and_api.md`](../docs/design/04_capcut_interchange_and_api.md): Đặc tả API REST & CapCut JSON Schema v3.
- [`docs/design/05_ui_ux_commentary_studio.md`](../docs/design/05_ui_ux_commentary_studio.md): Đặc tả giao diện Commentary Studio Web UI.

---

## 🖥️ GIAO DIỆN WEB UI (COMMENTARY STUDIO)

Giao diện Studio trực quan (Dark theme) phục vụ tại `http://localhost:8001/` gồm 3 cột làm việc thời gian thực:
- **Cột 1 (Input & Persona):** Dán link YouTube Shorts/Reels/TikTok hoặc kéo thả trực tiếp file MP4; chọn Persona biên kịch và ngôn ngữ.
- **Cột 2 (Visual Truth & Audio Inspector):** Xem bức ảnh lưới Contact Sheet 3x3 (in sẵn mốc giây), trạng thái câu thoại (Whisper VAD) và nhật ký hành động khách quan.
- **Cột 3 (Commentary Studio & Exporter):** Sửa trực tiếp kịch bản 4 nhịp (Hook, Build-up, Climax, Payoff), nghe thử hiệu ứng âm thanh SFX thật từ thư viện, đổi Persona viết lại trong 1s, tải file CapCut JSON v3 và phụ đề SRT.

---

## 🚀 HƯỚNG DẪN CÀI ĐẶT & CHẠY ỨNG DỤNG

### 1. Yêu cầu hệ thống
- **Python 3.10+**
- **FFmpeg & ffprobe** (đã cài đặt trong hệ thống và nhận lệnh `ffmpeg` từ Terminal).

### 2. Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường (`.env`)
Chỉnh sửa file `.env` (đã sao chép sẵn từ mẫu cấu hình):
```env
DEFAULT_AI_PROVIDER=custom
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.ai-box.vn/v1
DEFAULT_VISION_MODEL=gpt-4o-mini
DEFAULT_TEXT_MODEL=gpt-4o-mini
PORT=8001
```

### 4. Khởi động Web Server & Truy cập Studio
Chạy qua script:
```bash
.\run.bat
```
Hoặc qua lệnh trực tiếp:
```bash
python main.py
```
- **Giao diện Commentary Studio:** `http://localhost:8001/`
- **Swagger API Documentation:** `http://localhost:8001/docs`

### 5. Chạy kiểm thử tự động (Unit Tests)
```bash
.\run.bat test
```
*(Hiện tại 18/18 tests đã vượt qua thành công 100%).*
