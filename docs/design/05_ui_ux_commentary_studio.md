# 05. THIẾT KẾ GIAO DIỆN & TRẢI NGHIỆM NGƯỜI DÙNG (COMMENTARY STUDIO UI/UX)

## 1. TỔNG QUAN GIAO DIỆN
Giao diện **Commentary Studio** được thiết kế theo phong cách Dark Mode chuyên nghiệp dành cho Editor và Creator. Bố cục chia thành 3 cột tương tác trực tiếp theo thời gian thực:

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 🎬 AI VIDEO COMMENTARY STUDIO              [Skill: The Curiosity Explainer ▼]   [AI: Online (4o-mini)]  │
├────────────────────────┬───────────────────────────────────────────┬───────────────────────────────────┤
│ 1. ĐẦU VÀO & PERSONA   │ 2. THỊ GIÁC & ÂM THANH (TRUTH FIRST)      │ 3. STUDIO BIÊN TẬP LỜI BÌNH       │
│                        │                                           │                                   │
│ [ Dán link Shorts/Reels]│ 📸 LƯỚI ẢNH 3x3 (9 KHUNG HÌNH IN MỐC GIÂY):│ ⏱️ THỜI LƯỢNG: 45s (94 TỪ)       │
│ - HOẶC -               │ ┌────────┬────────┬────────┐              │ ⚡ TỐC ĐỘ: 125 WPM (CHUẨN)        │
│ [📁 Kéo thả file MP4]  │ │ 00:02  │ 00:07  │ 00:12  │              │ --------------------------------- │
│                        │ ├────────┼────────┼────────┤              │ [1] HOOK (00:00 - 00:04.5)        │
│ 🎯 CHỌN SKILL BIÊN KỊCH:│ │ 00:17  │ 00:22  │ 00:27  │              │ • Lời bình: [Chỉnh sửa trực tiếp] │
│ (●) 🧪 Explainer       │ ├────────┼────────┼────────┤              │ • Chữ nổi: [NƯỚC SÔI KHÔNG CẦN LỬA]│
│ (○) 🎬 Storyteller     │ │ 00:32  │ 00:37  │ 00:42  │              │ • SFX: 🔊 [Sub Boom] ▶ Nghe thử   │
│ (○) ✨ Satisfying      │ └────────┴────────┴────────┘              │                                   │
│ (○) 🎭 Witty & Twist   │                                           │ [2] BUILD-UP (00:04.5 - 00:18)    │
│                        │ 🎙️ ÂM THANH GỐC (WHISPER VAD):             │ • Lời bình: ...                   │
│ 🌐 NGÔN NGỮ:           │ • Trạng thái: [⚠️ Cắt đầu - TRUNCATED]    │ • SFX: 🔊 [Whoosh Fast] ▶ Nghe thử│
│ [ Tiếng Việt  ▼ ]      │ • Thoại: "...bởi vì áp suất bên trong..." │                                   │
│                        │                                           │ [3] CLIMAX & [4] PAYOFF ...       │
│ [ ⚡ PHÂN TÍCH & VIẾT ] │ 📝 NHẬT KÝ HÀNH ĐỘNG THỰC TẾ:             │ --------------------------------- │
│                        │ • 0-5s: Cốc thủy tinh rỗng gắn bơm chân... │ [🔄 Đổi Skill / Viết Lại (1s)]   │
│                        │ • 5-20s: Bọt khí li ti bùng nổ dữ dội...  │ [📋 Copy Toàn Bộ Voiceover]       │
│                        │ • 20-45s: Nước sôi đóng băng trên thành...│ [📥 Tải CapCut JSON] [📥 Tải SRT] │
└────────────────────────┴───────────────────────────────────────────┴───────────────────────────────────┘
```

---

## 2. CHI TIẾT 3 KHU VỰC TƯƠNG TÁC

### 2.1. Cột 1: Tiếp nhận Video & Cấu hình Persona
* **Chuyển đổi linh hoạt (Tabs):**
  - Tab 1: Nhập đường link (YouTube Shorts, TikTok, Reels) $\rightarrow$ Server tự động tải video chất lượng 720p/1080p bằng `yt-dlp`.
  - Tab 2: Vùng kéo thả (*Drag & Drop Zone*) cho phép nạp trực tiếp file video MP4/MOV từ máy tính.
* **Danh sách Skill Radio Cards:**
  - Hiển thị đầy đủ tên, icon, mô tả phong cách và tốc độ đọc mục tiêu (~135 WPM).
  - Bấm chọn để kích hoạt Persona tương ứng ngay lập tức.
* **Bộ chọn ngôn ngữ:** Tiếng Việt (khẩu ngữ sắc bén) hoặc English (Spoken cadence).

### 2.2. Cột 2: Thị giác & Âm thanh (Visual Truth Inspector)
* **Smart Contact Sheet Viewer:**
  - Hiển thị trực tiếp bức ảnh lưới 3x3 (1920x1080) gồm 9 khung hình có in sẵn nhãn giây `[00:02]`, `[00:07]`...
  - Cho phép click vào ảnh để phóng to xem chi tiết trong tab mới.
* **Thẻ trạng thái âm thanh (Audio Hint Box):**
  - Hiển thị trạng thái nhận diện giọng nói: `COMPLETE` (xanh), `TRUNCATED_START/END` (cam cảnh báo), `NO_SPEECH` (xám).
  - Trích xuất câu thoại gốc đã lọc nhiễu dải tần.
  - Hiển thị hướng dẫn AI (*Guidance*): Thông báo rõ ràng rằng AI đã tự động dựa vào hình ảnh khi câu thoại bị đứt đoạn.
* **Nhật ký hành động (Action Timeline):**
  - Liệt kê các mốc giây và hành động vật lý khách quan do Vision LLM ghi nhận.

### 2.3. Cột 3: Studio Biên tập Lời bình CapCut
* **Thanh thông số thời gian thực (Meta Ribbon):**
  - Tổng thời lượng video (giây).
  - Tổng số từ của toàn bộ kịch bản.
  - Tốc độ đọc phát thanh (WPM): Tự động đổi màu xanh nếu nằm trong ngưỡng chuẩn (115–150 WPM), chuyển đỏ nếu quá nhanh.
* **4 Phân đoạn nhịp điệu (Hook, Build-up, Climax, Payoff):**
  - **Inline Editable Textarea:** Cho phép người dùng gõ sửa trực tiếp câu từ; hệ thống tự động cập nhật lại tổng số từ và chỉ số WPM theo thời gian thực.
  - **Text Overlay Badge:** Hiển thị chữ in hoa 3–5 từ nổi bật cùng vị trí (TOP_CENTER, CENTER, LOWER_THIRD).
  - **Trình nghe thử SFX tích hợp:** Nút bấm **🔊 Nghe thử** kết nối trực tiếp với backend (`/api/v1/sfx/audio/{sfx_id}`) để phát thử âm thanh thật trong thư viện WAV; đổi trạng thái sang **⏹️ Dừng** khi đang phát.
* **Thanh tác vụ nhanh (Quick Actions Toolbar):**
  - **Nút "🔄 Viết lại với Skill khác (1s)":** Cho phép đổi Persona và sinh lại toàn bộ lời bình trong chưa đầy 1 giây mà không tốn token đọc lại ảnh.
  - **Nút "📋 Copy Toàn bộ Voiceover":** 1-Click copy toàn bộ lời bình sạch vào Clipboard để dán nhanh vào CapCut TTS hoặc ElevenLabs.
  - **Nút "📥 Tải CapCut JSON v3":** Tải file JSON bảo toàn toàn bộ nội dung người dùng vừa sửa.
  - **Nút "📄 Tải Phụ đề .SRT":** Tải file phụ đề chuẩn thời gian để kéo vào timeline dựng phim.

---

## 3. THIẾT KẾ CÔNG NGHỆ FRONTEND
* **Vanilla JavaScript & CSS3 thuần túy:** Không phụ thuộc vào framework nặng nề (React/Vue build tool), khởi chạy tức thì và bảo đảm tốc độ phản hồi cực nhanh.
* **Responsive Layout:** Tự động co giãn mượt mà từ màn hình laptop 13 inch đến màn hình làm việc 2K/4K 27 inch.
