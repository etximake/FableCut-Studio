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
│                        │ • 0-5s: Cốc thủy tinh rỗng gắn bơm chân... │ [🎧 VOICEOVER PLAYER (nếu có)]    │
│                        │ • 5-20s: Bọt khí li ti bùng nổ dữ dội...  │ ───────────────────────────────────│
│                        │ • 20-45s: Nước sôi đóng băng trên thành...│ MENUBAR CHÂN CỘT (1 hàng, 3 nhóm): │
│                        │                                         │ [📤 XUẤT][🖼️ MEDIA][🛠️ HÀNH ĐỘNG]   │
└────────────────────────┴───────────────────────────────────────────┴───────────────────────────────────┘
```
(Lưu ý: danh sách kịch bản [1]…[4] có thể dài bất kỳ — cột 3 cuộn nội bộ tại `.segments-list`, còn meta ribbon (trên) và menubar (dưới) luôn cố định.)

### 1.1. Nguyên tắc "Studio Lock" (khóa viewport, không scroll trang)
Từ bản cập nhật studio-lock-1, giao diện chuyển sang bố cục **khóa chiều cao theo viewport** — tương tự các phần mềm dựng phim (Premiere, CapCut desktop):

* **Trang không scroll** trên màn hình desktop (≥ 1051px): `body { height: 100vh; overflow: hidden }`, 3 cột `.panel` cố định `height: 100%` trong `.main-studio` (grid, `height: calc(100vh − topbar)`, `overflow: hidden`).
* **Mỗi cột tự cuộn nội bộ** khi nội dung vượt quá chiều cao hiển thị (`.panel-body--scroll` cho cột 1, body cột 2 là vùng scroll, cột 3 chỉ `.segments-list` scroll — meta ribbon, voiceover player, action bar luôn ở vị trí cố định).
* **Nút hành động chính không bao giờ chìm dưới nội dung**:
  - Cột 1: nút "⚡ Bước 1: Phân tích video" nằm trong `.input-panel-footer` — cố định dưới đáy cột, cách ly khỏi vùng scroll của body.
  - Cột 3: thanh `.studio-actions` (3 nhóm có nhãn) cố định dưới đáy cột.
* **Scroll trang trả lại cho màn hình hẹp** (< 1051px → 2 cột, < 721px → 1 cột): `body` mở `overflow: auto`, các cột giải phóng `height` để nội dung trải dài tự nhiên.

---

## 2. CHI TIẾT 3 KHU VỰC TƯƠNG TÁC

### 2.1. Cột 1: Tiếp nhận Video & Cấu hình Persona
Cột 1 được chia thành **4 nhóm (section) có tiêu đề**, mỗi nhóm là một khối nội dung gọn gàng bên trong vùng cuộn nội bộ của cột:

1. **📥 Nguồn video** — Tabs chuyển đổi linh hoạt:
   - Tab 1: Nhập đường link (YouTube Shorts, TikTok, Reels) $\rightarrow$ Server tự động tải video chất lượng 720p/1080p bằng `yt-dlp`.
   - Tab 2: Vùng kéo thả (*Drag & Drop Zone*) cho phép nạp trực tiếp file video MP4/MOV từ máy tính.
2. **🧠 Biên kịch & mô tả**
   - **Danh sách Skill Radio Cards:** hiển thị đầy đủ tên, icon, mô tả phong cách và tốc độ đọc mục tiêu (~135 WPM); bấm chọn để kích hoạt Persona tương ứng ngay lập tức.
   - Ba ô mô tả tự khai (máy/vật chính, hoạt động, điểm quan trọng) — chỉ bổ sung bối cảnh, không ép vào Vision LLM.
3. **🎯 Bước 2: Chốt dựng** (hiện sau khi phân tích xong — `#step2Section`, chỉ `display:block` khi `analyzeVideo()` thành công):
   - **Cảnh đã chọn (scene list)** — chỉ hiện khi `needs_scene_selection=true` và có `scene_proposal` (video > `MAX_SHORT_SECONDS`):
     - Mỗi dòng: checkbox (mặc định tick) + input số `start`/`end` (step 0.1s) + giây + lý do (mô tả ngắn từ block timeline).
     - Nút "Khôi phục gợi ý của AI" (`resetSceneProposal`) đưa về `sceneProposal` gốc.
     - Cảnh báo tổng thời lượng: `Đã chọn N cảnh, tổng X.Xs / tối đa Y.Ys.`; lỗi đầu tiên hiện ở `#sceneWarning` và vô hiệu nút "Viết kịch bản".
     - Kiểm tra: `0 ≤ start < end ≤ duration + 0.01`, không chồng, tổng ≤ `sceneMaxSeconds` (src/analyzer/scene_selector.py:39–66 + static/app.js:268–294).
   - **Template cards (chốt template dựng)** — render từ `GET /api/v1/templates` (6 template):
     - Mỗi card: tên (VI), mục tiêu cảm xúc (`FEELING_LABELS`: Thu hút/thỏa mãn/hiểu ra), mục đích + `best_for`.
     - Badge "★ AI gợi ý" trên card khớp `template_recommendation.template_id`.
     - Click card → `selectTemplate(id)`; đổi template thì **reset Direction** (bản cũ không còn đúng template).
     - `#templateWarning`: nếu template chọn cần tín hiệu mà `evidence_signals` chưa cho thấy → cảnh báo (mirror `_TEMPLATE_REQUIRED_SIGNAL` trong commentary_engine.py).
     - `#templateRecommendationNote`: giải thích lý do AI gợi ý hoặc lý do người dùng chọn khác.
   - **Ngôi kể lời bình (narrator select)** — `third_person` (mặc định), `second_person_hook`, `minimal_narrator`. Giá trị mặc định do `TEMPLATE_VOICE_DEFAULTS[template_id]` (src/analyzer/commentary_engine.py:62–93).
   - **Bản Định hướng (Direction)** — khối `#directionSection`:
     - Nút "Tạo bản Định hướng" → `POST /commentary/direction` → render `#directionForm` (promise, key moment, beats (purpose/overlay/SFX/pace/edit_guidance cho từng beat), sound_note).
     - Mỗi beat row: header beat + mốc giây, input purpose, input overlay text, input SFX, select pace (slow/normal/brisk), input edit_guidance, dòng "Bằng chứng: ...".
     - Khi Direction `source="fallback"`: `#directionStatus` hiện cảnh báo "Bản này suy ra bằng quy tắc vì LLM không trả được; hãy kiểm tra kỹ."
     - `readDirectionFromForm()` gom dữ liệu form → gửi kèm `generate-script` (trường `direction`, `source` đổi thành `user`).
   - Nút **"🎙️ Viết kịch bản theo template đã chốt"** → `POST /commentary/generate-script` (scenes + direction + template + narrator + TTS).
4. **🔊 Lồng tiếng & ngôn ngữ**:
   - **Bộ chọn ngôn ngữ:** English (mặc định, TTS tối ưu) hoặc Tiếng Việt. Đổi ngôn ngữ tự động chuyển giọng TTS tương ứng (en → `am_adam`, vi → `vi-*`).
   - Hộp cấu hình TTS (tắt/bật, chọn giọng, tốc độ đọc 0.8–1.3x). Danh sách giọng từ `GET /tts/voices` (Kokoro-82M local ONNX: am_adam/bm_george/af_bella/am_michael/bf_emma; Edge-TTS cloud: en-US-ChristopherNeural + vi-*). Badge `[Local Kokoro]` / `[Cloud Edge]` ở mỗi option.

Nút **"⚡ Bước 1: Phân tích video"** nằm trong `.input-panel-footer` — cố định dưới đáy cột 1, luôn thấy được dù nội dung nhóm bên trên có dài bao nhiêu.

### 2.2. Cột 2: Thị giác & Âm thanh (Visual Truth Inspector)
* **Smart Contact Sheet Viewer:**
  - Hiển thị trực tiếp bức ảnh lưới 3x3 (1920x1080) gồm 9 khung hình có in sẵn nhãn giây `[00:02]`, `[00:07]`...
  - Cho phép click vào ảnh để phóng to xem chi tiết trong tab mới.
  - Ảnh bị giới hạn `max-height: min(36vh, 380px)` để không chiếm trọn cột trong layout khóa viewport.
* **Thẻ trạng thái âm thanh (Audio Hint Box):**
  - Hiển thị trạng thái Audio Hint theo schema: `COMPLETE`, `TRUNCATED_START`, `TRUNCATED_END`, `TRUNCATED_BOTH`, `NO_MEANINGFUL_SPEECH`. UI tô xanh cho `COMPLETE`, cam cho các trạng thái có `TRUNCATED`, xám cho các trạng thái còn lại.
  - Trích xuất câu thoại gốc đã lọc nhiễu dải tần.
  - Hiển thị hướng dẫn AI (*Guidance*): Thông báo rõ ràng rằng AI đã tự động dựa vào hình ảnh khi câu thoại bị đứt đoạn.
* **Nhật ký hành động (Action Timeline):**
  - Liệt kê các mốc giây và hành động vật lý khách quan do Vision LLM ghi nhận.
  - Mỗi block là 1 hàng sửa được tại chỗ: nhãn `[start - end]` + tag bằng chứng (`evidence_source` + độ tin cậy %), **textarea** mô tả hành động và **select nguồn bằng chứng** với 4 giá trị `observed` (Đã thấy) / `heard` (Từ âm thanh) / `inferred` (Suy luận) / `unknown` (Chưa rõ) (schema: `Literal["observed","heard","inferred","unknown"]`, src/models/schemas.py:33).
  - Sửa mô tả hoặc đổi nguồn gọi `PATCH /api/v1/commentary/{video_id}/analysis` (body: `{"events": {"<index>": {"visual_action": ..., "evidence_source": ...}}}`, model `VisualTimelineUpdate`) để ghi lại timeline đã lưu — **không chạy lại Vision LLM** (src/api/routes.py:920–937).
  - Field `observable_changes` (biến đổi vật lý/thị giác quan sát được) có trong mỗi `ActionBlock` (src/models/schemas.py:31).
* **Kế hoạch dựng & cắt ghép (Edit Plan):**
  - Thanh timeline bar tỉ lệ (segment bar) + danh sách cut card. Danh sách cut tự cuộn nội bộ (`max-height: 340px`) để không đẩy các khối bên dưới ra khỏi màn hình.
  - Mỗi cut card hiện: vai trò kể (`role`: hook/setup/action/climax/payoff/transition — nhãn tiếng Việt Hook/Thiết lập/Hành động/Cao trào/Kết quả/Chuyển cảnh theo `EDIT_ROLE_LABELS`, static/app.js:782), mốc nguồn (`source_start`–`source_end` trên video gốc), mốc xuất (`output_start`–`output_end` trên timeline), reason, transition gợi ý (`suggested_transition`), tốc độ (`speed_factor`) và dòng `edit_guidance` (src/models/schemas.py:90–103).
  - Badge tổng thời lượng (`#editPlanBadge`: `X.Xs / Y.Ys gốc`) + dòng `#editPlanStrategy` (trường `narrative_strategy`, ví dụ "Kế hoạch cắt dựng theo mạch kể").
  - Ghi chú `#editPlanNote` = trường `trimmed_sections_note` (các đoạn thừa/chết đã lược bỏ khi chọn cảnh).
  - Khối edit plan ẩn hẳn khi `cuts` rỗng (video ngắn không cần cắt).
* **Toàn bộ cột 2 là 1 vùng cuộn nội bộ** (contact sheet → audio hint → timeline → edit plan): khi nội dung dài, người dùng cuộn *trong cột*, không làm kéo theo 2 cột bên cạnh.

### 2.3. Cột 3: Studio Biên tập Lời bình CapCut
* **Thanh thông số thời gian thực (Meta Ribbon):**
  - Tổng thời lượng video (giây).
  - Tổng số từ của toàn bộ kịch bản.
  - Tốc độ đọc phát thanh (WPM): Tự động đổi màu xanh nếu nằm trong ngưỡng chuẩn (115–150 WPM), chuyển đỏ nếu quá nhanh.
* **Thẻ phân đoạn kịch bản (segment cards) — số thẻ theo beat của template đã chốt, không còn cố định 4 nhịp Hook/Build-up/Climax/Payoff như thiết kế gốc:**
  - Vùng `.segments-list` là **vùng cuộn nội bộ duy nhất** của cột 3 (flex: `1 1 auto; overflow-y: auto`); meta ribbon đứng trên cùng, voiceover player + menubar nằm ở chân cột — cả hai luôn hiện thị, không bao giờ bị đẩy ra khỏi màn hình.
  - Số thẻ = số beat của template đã chốt: mỗi template trong `fablecut-bundle/presets/templates/` định nghĩa 4 beat (hazard-rescue = EMERGENCY/DIAGNOSIS/TREATMENT/RELIEF; before-after = BEFORE/TRANSITION/AFTER/VERDICT; how-it-works = QUESTION/STEP_1/STEP_2/STEP_3_RESULT; satisfying = SETUP/WORK/CLIMAX_SLOWMO/END; shock-hook = HOOK/REVEAL/PROOF/PAYOFF; story = CHARACTER/PROBLEM/TURN/PAYOFF). Mỗi thẻ là 1 `.segment-card` (static/app.js:964–1013).
  - **Header thẻ:** tag beat (`[HOOK]`, `[BEFORE]`…), badge vai trò (Hook/Thiết lập/Hành động/Cao trào/Kết quả/Chuyển cảnh — suy ra từ beat theo `EDIT_ROLE_LABELS`, static/app.js:782), mốc `[start - end]` trên timeline xuất ra, và tag **`Nguồn Xs–Ys`** (`source_time_range` — mốc tương ứng trên video gốc; ẩn khi không có, hiện khi đã chọn cảnh/cắt ghép).
  - **Inline Editable Textarea:** Cho phép người dùng gõ sửa trực tiếp câu lời bình; mỗi lần gõ cập nhật lại tổng số từ và chỉ số WPM theo thời gian thực (`updateSegmentVoiceover`, kèm `markScriptDirty` — SPEC-01).
  - **Khung phụ đề tiếng Việt (🇻🇳 GỢI Ý DỊCH TIẾNG VIỆT):** khối `.segment-vi-box` hiện `voiceover_vi_translation` (bản dịch nghĩa), `contenteditable` — click để sửa, blur gọi `updateSegmentViTranslation` (kèm `markScriptDirty`).
  - **Dòng chỉ dẫn dựng (✂️ Chỉ dẫn dựng):** hiện `edit_guidance` của segment (chỉ dẫn cắt/góc máy ngắn), chỉ hiện khi có giá trị.
  - **Footer thẻ:** Text Overlay Badge (🔤 `text_overlay.text` + vị trí TOP_CENTER/CENTER/LOWER_THIRD) và nút SFX.
  - **Trình nghe thử SFX tích hợp:** Nút bấm **🔊 Nghe thử** kết nối trực tiếp với backend (`/api/v1/sfx/audio/{sfx_id}`) để phát thử âm thanh thật trong thư viện WAV; đổi trạng thái sang **⏹️ Dừng** khi đang phát. Không có SFX thì hiện "NO SFX" (chữ thường, không phải nút).
  - **Nút "Viết lại beat này":** gọi `POST /api/v1/commentary/rewrite-segment` (chỉ Text LLM, không Vision) cho đúng beat đó, thay thẻ bằng segment mới + đánh dấu dirty (SPEC-01).
* **Menubar chân cột (`.editor-panel-footer`):**
  - Tách hoàn toàn khỏi vùng scroll của `panel-body`: chứa **voiceover player** (ẩn khi chưa có audio) + **thanh `.studio-actions`** 1 hàng, mật độ cao.
  - Thanh `.studio-actions` chia **3 nhóm có nhãn** nằm ngang (grid `1.05fr 1fr 0.95fr`; co 2 cột ở ≤ 1200px, 1 cột ở ≤ 720px):
    - **📤 Xuất:** Tải Trọn Gói (.ZIP), Tải CapCut JSON v3, Tải Voiceover (.WAV).
    - **🖼️ Media & phụ đề:** Tải Contact Sheet 3x3, Tải Thumbnail, Tải Video Gốc, Tải Subtitles Gốc (.SRT), Tải Subtitles Tiếng Việt (.SRT).
    - **🛠️ Hành động:** Viết lại với Skill khác (1s), Tạo lại Giọng Đọc, Copy Lời bình.
  - Nút **"💾 Lưu bản sửa"** và dòng trạng thái lưu (SPEC-01) do `app.js` inject (`ensureSaveBar`) vào nhóm **Hành động** — không còn chen vào hàng nút cũ.
  - Vì menubar đứng ngoài vùng cuộn, các nút xuất không bao giờ bị khuất sau danh sách kịch bản dài — dù có bao nhiêu beat, luôn bấm được.

---

## 3. THIẾT KẾ CÔNG NGHỆ FRONTEND
* **Vanilla JavaScript & CSS3 thuần túy:** Không phụ thuộc vào framework nặng nề (React/Vue build tool), khởi chạy tức thì và bảo đảm tốc độ phản hồi cực nhanh.
* **Responsive Layout:** Tự động co giãn mượt mà từ màn hình laptop 13 inch đến màn hình làm việc 2K/4K 27 inch.
* **Studio Lock (bản studio-lock-1):**
  - Desktop ≥ 1051px: `body` khóa `100vh` + `overflow: hidden`; `.main-studio` grid 3 cột `height: calc(100vh − topbar)`; mỗi panel `height: 100%`, nội dung cuộn nội bộ bằng class `.panel-body--scroll` (cột 1) / body cuộn (cột 2) / `.segments-list` cuộn (cột 3).
  - Nút hành động chính luôn cố định ngoài vùng cuộn: `.input-panel-footer` (cột 1) và `.studio-actions` (cột 3).
  - Breakpoint 1050px → 2 cột + trả scroll trang; breakpoint 720px → 1 cột + scroll trang; toolbar 3 nhóm co về 2 cột ở 1200px, 1 cột ở 720px.
  - `app.js` chỉ chỉnh 1 chỗ: `ensureSaveBar()` chuyển nút lưu sang `.actions-group--actions` (có fallback prepend nếu không tìm thấy nhóm).
