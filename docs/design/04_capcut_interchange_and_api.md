# 04. ĐẶC TẢ API & CAPCUT JSON SCHEMA (CAPCUT INTERCHANGE & API)

## 1. CAPCUT INTERCHANGE JSON SCHEMA (VERSION 3)

Đây là hợp đồng dữ liệu chuẩn đầu ra giữa hệ thống backend và các công cụ biên tập (CapCut Desktop, Premiere, CapCut HUD, và pipeline FableCut). **Lưu ý so với thiết kế gốc:**

- **Hợp đồng kiểm tra thực tế:** khi export, JSON được validate theo `fablecut-bundle/schema/input_schema.json` (Draft 7, **không phải** draft-2020-12 như thiết kế ban đầu, và không phải "CapCutCommentaryInterchangeV3" như thiết kế gốc). Schema này nằm trong `fablecut-bundle/` — chung cho cả FableCut (tầng biên dịch) và Analyst (tầng sinh kịch bản).
- **`schema_version`** trong schema FableCut là `minimum: 1` (không `const: 3` như thiết kế gốc). Pydantic model hiện gán mặc định `3` (src/models/schemas.py:207) nhưng schema không ép 3.
- **`beat`** trong schema FableCut cho phép tập beat **mở rộng** theo template (EMERGENCY, DIAGNOSIS, TREATMENT, RELIEF, HOOK, REVEAL, PROOF, PAYOFF, QUESTION, STEP_1, STEP_2, STEP_3_RESULT, SETUP, WORK, CLIMAX_SLOWMO, END, BEFORE, TRANSITION, AFTER, VERDICT, CHARACTER, PROBLEM, TURN, BUILD_UP, CLIMAX, `STEP_n`), thay vì 4 beat cố định HOOK/BUILD_UP/CLIMAX/PAYOFF như thiết kế gốc.
- **`sfx_cue`** là trường tùy chọn (`["object", "null"]`), không bắt buộc.
- **`voiceover_vi_translation`** là trường mới (bản dịch nghĩa tiếng Việt), bắt buộc cho mỗi phân đoạn theo quy tắc prompt (src/skills/base.py:176–177).
- **Mở rộng trong Pydantic model** (src/models/schemas.py:147–157): thêm `edit_guidance`, `source_time_range`, `style` — không có trong thiết kế gốc.
- **`video_metadata`** mở rộng thêm: `template_id`, `template_version`, `contact_sheet_file`, `thumbnail_file`, `voiceover_audio_file`, `voiceover_voice` (src/models/schemas.py:190–203).

Bên dưới là schema thiết kế gốc (về mặt nội dung, vẫn đúng cho phần lõi voiceover/overlay/sfx). Schema thực tế để so sánh: `fablecut-bundle/schema/input_schema.json`.

---

## 2. DANH SÁCH RESTFUL API ENDPOINTS

Base URL: `/api/v1` (router định nghĩa tại `src/api/routes.py:59`).

### Luồng 2 bước (Batch 2) — cách UI hiện tại chạy

| # | Method | Endpoint | Mô tả |
| :-- | :--- | :--- | :--- |
| 1 | `POST` | `/commentary/upload-video` | Tải file video MP4/MOV/MKV/WEBM từ máy tính lên `TEMP_DIR`, trả về `video_path` (dùng khi tab "Tải file"). |
| 2 | `POST` | `/commentary/analyze` | **Bước 1.** Tiền xử lý (Contact Sheet 3×3 + Audio Hint) → Chặng 1 Vision (mù) → `recommend_template` → `propose_scenes` (cho video > `MAX_SHORT_SECONDS`) → `build_edit_plan`. Trả về `AnalyzeResponse` (timeline + template + scene proposal + edit_plan), **chưa** viết kịch bản. |
| 3 | `POST` | `/commentary/direction` | **Tùy chọn ở Bước 2.** LLM viết bản Định hướng (promise, key moment, beats, overlay, SFX dự kiến) từ timeline đã chọn cảnh. Nếu LLM hỏng → fallback theo quy tắc (`source="fallback"`). |
| 4 | `POST` | `/commentary/generate-script` | **Bước 2.** Sinh kịch bản CapCut Interchange v3 theo template + Direction + skill đã chốt; chạy TTS nếu `enable_tts`; lưu DB + export (JSON/SRT/audio/video). |
| 5 | `POST` | `/commentary/{video_id}/script` | **SPEC-01.** Lưu bản kịch bản người dùng đã sửa (append phiên bản mới, validate trước khi ghi). |
| 6 | `GET` | `/commentary/{video_id}/script` | Đọc lại phiên bản kịch bản mới nhất. |
| 7 | `POST` | `/commentary/rewrite-segment` | Viết lại **1 beat** (partial rewrite) theo `segment_index`. |
| 8 | `PATCH` | `/commentary/{video_id}/analysis` | Sửa trực tiếp `ActionBlock` (visual_action, evidence_source…) trong timeline đã lưu. |

### Endpoint phụ trợ

| Method | Endpoint | Mô tả |
| :--- | :--- | :--- |
| `GET` | `/templates` | Danh sách 6 template + `narrator_mode`/`target_feeling` mặc định (enrich từ `TEMPLATE_VOICE_DEFAULTS`). |
| `GET` | `/skills` | Danh sách 5 Skill biên kịch (registry). |
| `GET` | `/tts/voices` | Catalog giọng đọc Kokoro-82M (local ONNX) + Edge-TTS (cloud). |
| `POST` | `/tts/synthesize` | Sinh/tạo lại voiceover cho kịch bản hiện hành, khớp lại phụ đề. |
| `POST` | `/commentary/export` | Tải file theo `format` (JSON, SRT, SRT_VI, WAV/MP3, Contact Sheet, Thumbnail, Video, Bundle ZIP). |
| `GET` | `/commentary/{video_id}/export?format=` | Tải trực tiếp file theo định dạng (tham số `format`). |
| `GET` | `/commentary/{video_id}/audio` | Phát/truy cập file voiceover WAV/MP3. |
| `GET` | `/images/contact-sheet/{video_id}` | Ảnh lưới 3×3 (tải từ exports hoặc TEMP_DIR). |
| `GET` | `/sfx/catalog` | Catalog hiệu ứng âm thanh (`assets/sfx_library/catalog.json`). |
| `GET` | `/sfx/audio/{sfx_id}` | Nghe thử file WAV SFX theo ID. |
| `GET` | `/ai/status` | Trạng thái provider, model, TTS (ONLINE/OFFLINE). |
| `POST` | `/ai/test/{model_type}` | Test nhanh model Vision hoặc Text (1 request tối giản). |

### Endpoint deprecated / legacy

| Method | Endpoint | Ghi chú |
| :--- | :--- | :--- |
| `POST` | `/commentary/process-video` | **Deprecated** (Batch 2). Luồng 1 nút chạy hết (analyze + script + TTS + export). UI không còn dùng; giữ cho API cũ. `routes.py:482`. |
| `POST` | `/commentary/rewrite` | Viết lại toàn bộ kịch bản với Skill/template khác (chạy lại Chặng 2 + TTS). UI hiện chuyển sang `generate-script` với `content_only=true`. |

---

## 3. CHI TIẾT CÁC ENDPOINT CHÍNH

### 3.1. Bước 1 — Phân tích video: `POST /api/v1/commentary/analyze`

Tiếp nhận `video_url` hoặc `video_path` (đã upload qua `/upload-video`). **Chỉ phân tích, chưa viết kịch bản.**

* **Request:**
```json
{ "video_url": "https://www.youtube.com/shorts/...", "video_path": null }
```

* **Quy trình nội bộ (src/api/routes.py:410–479):**
  1. Nếu là URL: tải video bằng `yt-dlp` → `TEMP_DIR`.
  2. `LocalVideoPreprocessor.process()` → Contact Sheet 3×3 + `AudioHint` + `duration`.
  3. `VisionActionEngine.extract_visual_timeline()` (Vision LLM **mù**: không nhận mô tả người dùng) → `VisualActionTimeline` + `evidence_signals`. Lưu DB.
  4. `recommend_template(timeline)` → `TemplateRecommendation` (decision tree theo evidence_signals). Gán `selected_template_id` + `template_selection_source` vào timeline, lưu DB lần 2.
  5. `propose_scenes(timeline, template, max_seconds)` → `scene_proposal` (mốc giây gốc) + `needs_scene_selection` flag + `max_scene_seconds`.
  6. `build_edit_plan(timeline, scene_proposal, template)` → `EditPlan` (cuts có `source_start/end`, `output_start/end`, `role`, `suggested_transition`, `speed_factor`, `edit_guidance`).
  7. Trả về `AnalyzeResponse`.

* **Response 200 (`AnalyzeResponse`, src/models/schemas.py:227–239):**
```json
{
  "status": "SUCCESS",
  "video_id": "vid_2026_test",
  "contact_sheet_url": "/api/v1/images/contact-sheet/vid_2026_test",
  "audio_hint": { "status": "TRUNCATED_START", "clean_text": "...", "guidance": "..." },
  "visual_timeline": { "evidence_signals": { "has_distinct_steps": true, "...": "..." }, "action_timeline": ["..."] },
  "template_recommendation": { "template_id": "how-it-works", "source": "recommended", "reason": "..." },
  "narrator_mode": "third_person",
  "target_feeling": "understanding",
  "scene_proposal": [ { "start": 10.0, "end": 25.0, "role": "hook", "reason": "..." } ],
  "max_scene_seconds": 60.0,
  "needs_scene_selection": false,
  "edit_plan": { "target_duration_seconds": 28.7, "cuts": ["..."] }
}
```

---

### 3.2. Bước 2 — Viết kịch bản: `POST /api/v1/commentary/generate-script`

Sinh kịch bản CapCut Interchange v3 từ timeline đã lưu (không chạy lại Vision). Người dùng chốt template, scenes, Direction, TTS.

* **Request (`GenerateCommentaryRequest`, src/models/schemas.py:366–381):**
```json
{
  "video_id": "vid_2026_test",
  "skill_id": "curiosity-explainer",
  "template_id": "how-it-works",
  "scenes": [ { "start": 10.0, "end": 25.0, "reason": "..." } ],
  "direction": { "promise": "...", "key_moment_start": 15.0, "beats": ["..."] },
  "language": "en",
  "enable_tts": true,
  "content_only": false,
  "tts_voice": "am_adam",
  "tts_speed": 1.0
}
```
- `scenes=null` → dùng lựa chọn đã lưu trong DB hoặc tự áp dụng proposal.
- `direction=null` → dùng bản Direction đã lưu hoặc tự sinh (ghi `review_note` cảnh báo).
- `content_only=true` → không TTS, không export video (dùng cho "Viết lại" nhanh).
- `enable_tts=true` + `content_only=false` → TTS + export file video ghép (nếu có scene).

* **Response 200 (`CommentaryGenerationResponse`):**
```json
{
  "status": "SUCCESS",
  "video_id": "vid_2026_test",
  "capcut_json": { "schema_version": 3, "segments": ["..."], "edit_plan": { "cuts": ["..."] } },
  "template_recommendation": { "template_id": "how-it-works", "source": "recommended" },
  "review_notes": ["Beat 3 có khoảng trống timeline trước 12.00s.", "..."],
  "story_angle": "Chủ thể: ...",
  "narrator_mode": "third_person",
  "target_feeling": "understanding",
  "qa_metadata": { "template_id": "how-it-works", "prompt_version": "simplified-batch1-v1", "model": "..." },
  "scenes_applied": [ { "start": 10.0, "end": 25.0 } ],
  "direction": { "promise": "...", "beats": ["..."] },
  "edit_plan": { "target_duration_seconds": 35.0, "cuts": ["..."] }
}
```

---

### 3.3. Bản Định hướng: `POST /api/v1/commentary/direction`

LLM viết bản Direction (kế hoạch beat) từ timeline + template. Người dùng sửa trực tiếp ở UI trước khi gọi `generate-script`.

* **Request (`DirectionRequest`):** `video_id`, `skill_id`, `template_id`, `description_*`, `narrator_mode`, `scenes`, `language`.
* **Response (`DirectionResponse`):** `direction` (promise, key_moment, beats, sound_note), `scenes_applied`, `original_duration_seconds`, `review_notes` (cảnh báo fallback, auto-applied scenes).
* **Nguồn Direction:** `source` ∈ `llm` / `fallback` / `user`. Khi `generate-script` nhận `direction` từ client, ghi `source="user"`.

---

### 3.4. Viết lại 1 beat: `POST /api/v1/commentary/rewrite-segment`

* **Request (`PartialRewriteRequest`):** `video_id`, `segment_index`, `current_voiceover` (optional), `instruction`, `skill_id`, `language`.
* **Response (`PartialRewriteResponse`):** `segment` (cập nhật `voiceover` + `voiceover_vi_translation`), `review_note`.
* **Hành vi:** Lấy `ActionBlock` tương ứng (cùng index) làm evidence; LLM Text (không Vision) viết lại 1 beat; validate + lưu DB.

---

### 3.5. Lưu bản sửa (SPEC-01): `POST /api/v1/commentary/{video_id}/script`

* **Request:** Body là **toàn bộ** `CapCutCommentaryInterchange` (đúng hình dạng UI đang giữ).
* **Validate:** `validate_interchange()` theo `fablecut-bundle/schema/input_schema.json` (Draft 7) → 422 nếu sai.
* **Lưu:** `db.save_commentary_script()` → append phiên bản mới (`saved_version`).
* **Export lại:** `exporter.export(script)` → file JSON/SRT/SRT_VI cập nhật trên đĩa.

---

### 3.6. Deprecated — Luồng 1 nút: `POST /api/v1/commentary/process-video`

Giữ nguyên cho API cũ. Chạy hết: Preprocess → Vision → Template → Scene auto → Script → TTS → Export.
`token_usage` trả về là **giá trị cố định** 1050/420/1470 (src/api/routes.py:620–624), không phải số đo thực từ provider.

---

## 4. TÍCH HỢP VỚI PIPELINE FABLECUT VÀ CAPCUT

File JSON v3 xuất ra được dùng bởi **hai hệ thống** (không còn chỉ là CapCut HUD như thiết kế gốc):

1. **Pipeline FableCut (chính):** JSON được validate theo `fablecut-bundle/schema/input_schema.json` (Draft 7) trước khi ghi file (`src/exporter/capcut.py:13–31`). Sau đó `fablecut-bundle/adapter/convert.py` đọc JSON → sinh ops `fablecut_patch_project` → FableCut MCP server render 9:16 MP4. Trùng khớp với tài liệu `fablecut-bundle/AGENTS.md` (Buoc 6–7).
2. **CapCut Desktop / HUD (phụ):** File `.capcut.json` + `.srt` + `.srt_vi` + audio WAV + video MP4 + thumbnail được đóng gói thành **Bundle ZIP** (`format=bundle_zip`) để kéo vào CapCut:
   - **1-Click Copy:** Nút "📋 Copy Lời bình" trên UI copy toàn bộ voiceover vào clipboard → dán vào Text-to-Speech của CapCut PC.
   - **SFX:** `sfx_cue.suggested_sfx` trỏ tên file trong `assets/sfx_library/` (catalog tại `catalog.json`).
   - **Phụ đề:** File `_subtitles.srt` (ngôn ngữ chính) + `_subtitles_vi.srt` (bản dịch nghĩa) với mốc giây khớp mili-giây.
   - **Video gốc / clip ghép:** File `{video_id}.mp4` trong exports — nếu đã chọn cảnh, file này là clip ghép (re-encode), không phải video gốc (bản gốc được giữ riêng qua `_preserve_original_video`).

### Đồng bộ sang `fablecut-data/media/`
Khi `EXPORTS_DIR` (hoặc `FABLECUT_MEDIA_DIR`) trỏ vào thư mục **khác** `fablecut-data/media/`, `exporter.export()` có cờ `sync_to_fablecut_data=True` (hiện chưa dùng trong code, nhưng đã viết sẵn) để copy file vào `fablecut-data/media/<video_id>/` (src/exporter/capcut.py:238–255). Theo `AGENTS.md` monorepo, dữ liệu runtime nằm ở `fablecut-data/` và được gitignore.

### Edit Plan & Source Time Range
- **`edit_plan`** (nguyên nhân thiết kế Batch 1/2): kế hoạch cắt dựng chi tiết cho editor, gồm `narrative_strategy`, `cuts` (mỗi cut có `role`, `source_start/end` (giây trên video gốc), `output_start/end` (giây trên timeline xuất ra), `suggested_transition`, `speed_factor`, `edit_guidance`). UI render timeline bar + cut cards ở cột 2.
- **`source_time_range`** trên mỗi `CommentarySegment`: mốc tương ứng trên **video gốc** (không phải clip ghép), để editor biết quay về đoạn nào khi dựng. Khi có scenes, `_map_to_source_range()` (src/analyzer/commentary_engine.py:688–710) ánh xạ mốc clip → mốc gốc; segment bắc qua splice thì lấy đoạn nguồn có phần giao dài nhất.
- **`edit_guidance`** trên mỗi segment: chỉ dẫn cắt/góc máy ngắn (2–3 từ), có 3 nguồn: Direction beat → Edit Plan cut → mặc định theo vai trò beat.
