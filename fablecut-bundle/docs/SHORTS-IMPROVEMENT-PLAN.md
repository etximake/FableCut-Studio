# Kế Hoạch Cải Tiến Pipeline YouTube Shorts 9:16 (`1080x1920`)

> **Phiên bản kế hoạch**: `1.1.0` · **Cập nhật trạng thái**: `2026-11-12`  
> **Phạm vi**: `fablecut-bundle` · `fablecut-data` · `youtube-analyst-niches-forest` (giữ nguyên đọc-only toàn bộ repo `FableCut`)  
> **Mục tiêu cốt lõi**: Xây dựng pipeline dựng Shorts `1080x1920` (9:16) **xác định (deterministic), an toàn vùng hiển thị (Safe-Box), hiển thị ngay Frame 0, đạt chuẩn âm thanh `-14 LUFS / <= -1.0 dBFS`, và kiểm soát chất lượng tự động (QA Gate)** trước khi sản xuất hàng loạt.

---

## 1. Kiến trúc & Nguyên tắc Bất biến

```text
[youtube-analyst-niches-forest]        [fablecut-bundle]                  [FableCut + fablecut-data]
  Chặng 1: Contact Sheet 3x3             schema/input_schema.json            FableCut/ (READ-ONLY)
  Chặng 2: Commentary + Template  --->   presets/templates/*.json     --->   mcp-server.js (stdio)
  Chặng 3: TTS + Export/Sync             presets/styles.json                 fablecut-data/
           (media/<video_id>/)           adapter/convert.py                    ├── media/<video_id>/
                                         scripts/qa_check.py                   ├── library/{sfx,svg}/
                                         cleanup.py                            └── exports/ (mp4 9:16)
```

### Ràng buộc bắt buộc
1. **Không đụng vào mã nguồn `D:\HOANG HA\Deverlopper Software\FableCut`**: Mọi tệp lõi (`server.js`, `mcp-server.js`, `app.js`, `project-ops.js`, `templates.js`, `edit-ops.js`, `mask.js`, `audio-fx.js`, `color.js`, `delivery.js`, `paths.js`, `media-lib.js`) phải giữ nguyên vẹn 100%.
2. **Dựng timeline xác định (Deterministic)**: Toàn bộ cấu trúc track, thời gian, chữ, mask, SVG, SFX, màu và audio FX do `adapter/convert.py` sinh từ JSON đầu vào đã qua kiểm duyệt + preset chuẩn hóa. Không dùng LLM tự sinh raw `fablecut_patch_project` ops, không tích hợp Remotion TSX hay chạy lại Whisper.
3. **Cách ly dữ liệu theo `video_id`**: Tài nguyên đầu vào nằm tại `fablecut-data\media\<video_id>\`; file trung gian trong `youtube-analyst-niches-forest\temp\` tự xóa sau khi export; tuyệt đối bảo vệ `fablecut-data\exports\`, `library\`, và `projects\`.
4. **Chuẩn chất lượng Shorts**:
   - **Beat-1 Frame-0 visibility**: Beat đầu tiên phải thấy rõ ngay tại Frame 0 (`local = 0`), không `transitionIn`, không preset `IN`/`OUT`, `textAnim` thuộc nhóm hiển thị ngay Frame 0.
   - **Vùng an toàn (`900x1400`)**: `top >= 120px`, `bottom >= 320px`, `right >= 120px`, `left >= 60px` trên khung `1080x1920`.
   - **Giữ nhịp thị giác (Retention)**: Cắt nhỏ `V1` cho mọi beat `> 5s`, thêm chuyển động/zoom nhẹ hoặc rung tác động, không dùng CTA outro kéo dài ở cuối.
   - **Hook không âm thanh (Sound-off)**: Headline ngắn 3–6 từ rõ nét ngay mở đầu + phụ đề/overlay tương phản cao.
   - **Âm thanh chuẩn phát hành**: SFX trên `A2` chống chồng chéo `< 0.4s`, phân tầng gain (`A1` voiceover > `A2` SFX > `V1` ambient), export đạt `-14 LUFS` và true peak `< -1.0 dBFS`.
5. **Skill chỉ điều phối & QA**: `shorts-orchestrator` chỉ chứa quy trình gọi công cụ và checklist kiểm tra, không nhồi logic code vào prompt; kèm 1 dòng con trỏ trong `AGENTS.md`.
6. **Git hygiene**: Không commit bất kỳ workspace nào cho đến khi hoàn thành kiểm thử toàn diện và được xác nhận.
7. **Cảnh báo bảo mật (`CHECKLIST.md`)**: `9Router` hiện đang bind `0.0.0.0` và chưa xác nhận `JWT_SECRET` — giữ nguyên cảnh báo trong báo cáo, không tự ý thay đổi cấu hình bảo mật hệ thống.

---

## 2. Hiện trạng hệ thống (Đã xong vs. Tồn đọng)

### 2.1 Đã hoàn thành trên đĩa
- **`youtube-analyst-niches-forest`**:
  - Cô lập xuất file theo `EXPORTS_DIR\<video_id>\` (`src/core/config.py`, `src/exporter/capcut.py`, `src/tts/tts_engine.py`).
  - Tự động dọn file tạm qua `cleanup_video_temp_files` trong endpoint `POST /api/v1/commentary/process-video` (`src/api/routes.py`), bộ test backend hiện đạt `24/24`.
- **`fablecut-bundle`**:
  - Tạo `cleanup.py` và `cleanup.bat` hỗ trợ dọn theo lô `temp/` + `media/<video_id>/` + cache phân tích mà vẫn bảo vệ `exports/`, `library/`, `projects/` và media thuộc `project.json` đang mở.
  - Tạo `presets/templates/index.json` (`registry_version: "1.1.0"`, cây quyết định 7 bước) và đủ 6 template `v1.1.0`: `hazard-rescue.json`, `shock-hook.json`, `how-it-works.json`, `satisfying.json`, `before-after.json`, `story.json`.
  - Tạo `presets/styles.json` gồm 14 style (`HIGHLIGHT_YELLOW`, `highlight-yellow`, `IMPACT_RED`, `BOLD_RED`, `CLEAN_WHITE`, `clean-white`, `NEON_GLOW`, `neon-glow`, `BOLD_CONTRAST`, `bold-contrast`, `HANDWRITTEN_WARM`, `handwritten-warm`, `CLEAN_CYAN`, `ELEGANT_GOLD`) với `boxW: 820`, `boxFit: true`, `vAlign: "middle"`.
- **`fablecut-data`**:
  - Relink media trong `project.json` (`revision: 40`, `1080x1920 @ 30fps`): `m_re9jh8n` (`snaptik.vn_7611044561959324946.mp4`, `31.438s`, `576x1024`) và `m_stklyr6` (`AI Video Commentary _ CapCut Engine Studio.wav`, `33.04s`).
  - Bổ sung SVG `step-1.svg`, `step-2.svg`, `step-3.svg` (`280x96`) vào `fablecut-data/library/svg/` (cùng với `checkmark-success.svg` `400x400`, `underline-swoosh.svg` `600x120`).
  - Bổ sung `soft_chime.wav` vào `youtube-analyst-niches-forest/assets/sfx_library/ui_and_accents/` và `fablecut-data/library/sfx/`, đồng thời chuẩn hóa toàn bộ 21 file `.wav` trong `fablecut-data/library/sfx/`.

### 2.2 Vấn đề / Lỗ hổng đã xác minh qua kiểm toán mã nguồn
1. **`schema/input_schema.json`**: Schema đã hỗ trợ hợp đồng interchange hiện tại và thêm alias transition `slide` / `whip-pan`; cần tiếp tục kiểm chứng khi mở rộng các enum.
2. **`adapter/convert.py`**:
   - Các lỗi compiler đã xử lý: motion và speed_ramp từ template, transition chỉ gắn cut đầu beat, SFX có fallback/layout và duration theo cue, split-screen có offset/label, và SVG được đặt tránh vùng chữ TOP_CENTER.
   - Chưa ưu tiên đọc `presets/templates/` trước `presets/video-templates-5/templates/`.
   - Chưa xóa clip cũ trên timeline mở (`removeClip`) trước khi dựng mới, dễ gây rác/đè clip khi chạy lại.
   - Chưa có fallback tìm media kiểu `*<video_id>*` (ví dụ JSON mẫu ghi `video_id: "7611044561959324946"` trong khi thư mục thực tế là `snaptik.vn_7611044561959324946/`, và thiếu `voiceover_audio_file`).
   - Compiler hiện chuyển animation ẩn ở beat đầu về hiệu ứng hiển thị frame-zero đã allowlist.
   - Compiler hiện ánh xạ vị trí text và kẹp tọa độ/hộp chữ trong vùng an toàn.
   - QA hiện kiểm tra V1 cuts, SFX anti-overlap, split-screen, SVG/text separation, template fonts và first-frame; cần vẫn render/inspect thực tế trước khi tuyên bố template đạt.
3. **Ví dụ mẫu (`examples/`)**:
   - 5 file `irrigation-*.json` vẫn đang nằm ở `presets/video-templates-5/examples/` với `template_version: "1.0.0"` và thiếu `irrigation-hazard-rescue.json`.
   - File legacy `examples/upload_snaptik.vn_7611044561959324946_commentary.capcut.json` có `time_range` không liên tục (`[0..4.16]`, `[4.5..17.5]`, ...) — schema cần giữ tương thích hợp lệ cho fixture này, trong khi QA gate cảnh báo hoặc siết chặt ở luồng mới.
4. **`youtube-analyst-niches-forest`**:
   - `src/models/schemas.py`: Thiếu `QUESTION`, `REVEAL`, `PROOF`, `TRANSITION`, `VERDICT`, `CHARACTER`; `normalize_style` ép toàn bộ 14 style về 3 tên cũ (`HIGHLIGHT_YELLOW`, `BOLD_RED`, `CLEAN_WHITE`); `SFXCue` chưa nullable; `template_version` đang để `"1.0.0"`; thiếu trường root `template_id`, `template_version`, `note` và `CommentarySegment.style`.
   - `src/analyzer/commentary_engine.py` dòng 94–110: Map `skill_to_template` chứa key không tồn tại trong `registry.py` (`"satisfying-artisan"`, `"before-after"`, `"story"` thay vì `"satisfying-narrator"`, `"suspense-storyteller"`, `"witty-commentator"`), hardcode `"template_version": "1.0.0"`, và chưa truyền cấu trúc beat của template được chọn vào prompt cho LLM.
   - `src/tts/tts_engine.py`: Cursor tuần tự nay giữ time ranges liền mạch và giới hạn theo thời lượng video.
   - `src/exporter/capcut.py` dòng 171: Chỉ tìm beat `CLIMAX`, `CLIMAX_SLOWMO`, `HOOK`, `SETUP` để cắt thumbnail — bỏ sót beat của `hazard-rescue`, `how-it-works`, `shock-hook`, `before-after`, `story`.
   - `assets/sfx_library/catalog.json`: Đã khai báo `soft_chime` cùng canonical IDs; route giữ alias cũ `sfx_impact_sub_boom`.
   - `src/api/routes.py`: Thiếu `GET /api/v1/templates`, thiếu `template_id` trên `CommentaryRequest` & `RewriteRequest`, và hàm `rewrite_commentary` chưa gọi `cleanup_video_temp_files`.
   - `static/index.html` & `static/app.js`: Thiếu dropdown chọn `template_id`, và `app.js` dòng `391`, `416` truy cập `seg.sfx_cue.suggested_sfx` trực tiếp (sẽ lỗi JS nếu `sfx_cue` là `null`).
5. **Còn lại**: Skill `shorts-orchestrator`, render kiểm chứng trực quan cho 6 template, và chọn 3 template mặc định kênh. `scripts/qa_check.py` đã được thêm và chạy trên fixtures.

---

## 3. Hợp đồng kỹ thuật `FableCut` đã kiểm chứng trực tiếp từ mã nguồn

Mọi thông số dưới đây được đọc trực tiếp từ `D:\HOANG HA\Deverlopper Software\FableCut\`:

| Thành phần | Quy tắc xác minh từ code `FableCut` | Nguồn |
|---|---|---|
| **Hệ tọa độ khung hình** | `ctx2d.translate(W/2, H/2)` rồi `translate(p.x, p.y)`. Tâm `(0, 0)` chính là pixel `(540, 960)` trên canvas `1080x1920`. | `app.js:12856-12859` |
| **Safe-Box `900x1400`** | Biên an toàn màn hình: `x in [60, 960]` (`right >= 120px`), `y in [120, 1600]` (`top >= 120px`, `bottom >= 320px`). Với `boxW = 820`, `x = 0` chiếm `[130, 950]` (lọt trọn). Với `boxH`, `p.y` phải nằm trong `[-(960-120)+boxH/2, (960-320)-boxH/2]` = `[-840+boxH/2, +640-boxH/2]`. | `app.js:12856`, `15501-15534` |
| **TextBox tự co chữ** | Khi `boxW > 0 && boxH > 0 && boxFit: true`, `fitFontSizeToBox()` tự giảm `fontSize <= max` để vừa khít hộp; `vAlign` nhận `"top" \| "middle" \| "bottom"`. | `app.js:15439-15533` |
| **Hiển thị Frame 0 (`textAnim`)** | **Hiện ở `local=0`**: `none`, `highlight`, `karaoke`, `wave`, `bounce`, `shake`, `font-cut`.<br>**ẨN ở `local=0`** (`u <= 0` return / `budget = 0`): `clip-reveal`, `zoom-in`, `rise-mask`, `typewriter`, `letter-pop`, `word-pop`, `word-slide`. | `app.js:15604-15774` |
| **Preset Animation (`applyPreset`)** | Nhóm `IN` (`fade-in`, `pop-in`, `slide-*-in`, `drop-in`, `zoom-in`, `spin-in`, `whip-in`, `rise-blur`, `draw-on`) bắt đầu ẩn/ngoài khung ở `t=0` -> **CẤM dùng cho Beat 1**. Nhóm `AT` (`pulse`, `shake`, `wobble`, `bounce`, `flash`) và `LOOP` (`float`, `breathe`, `sway`, `spin`, `wiggle`) giữ nguyên Frame 0 hiển thị -> an toàn cho Beat 1. | `templates.js:57-115` |
| **SVG Overlay (`fit`)** | Mặc định `fit: "contain"` sẽ phóng to SVG `280x96` kín chiều ngang `1080px`. Phải đặt `props.fit = "none"` kèm `x`, `y`, `scale` để vẽ đúng kích thước thiết kế. | `app.js:11715, 12812, 12919` |
| **Filter Presets (`filterPreset`)** | Hợp lệ: `none`, `cinematic`, `teal-orange`, `noir`, `vintage`, `faded`, `warm`, `cold`, `pop`, `dreamy`, `retro`, `bw-soft`, `cyberpunk`, `sunset`, `midnight`. | `app.js:94-110` |
| **Transitions (`transitionIn`)** | Hợp lệ: `none`, `fade`, `slide-left`, `slide-right`, `slide-up`, `slide-down`, `zoom`, `wipe`, `wipe-right`, `wipe-up`, `wipe-down`, `iris`, `spin`, `blur`, `whip`, `glitch`, `pop`. Beat 1 luôn là `"none"`; mỗi beat chỉ gắn transition vào cut V1 đầu tiên. | `app.js:86-88` |
| **Masks (`props.masks`)** | `shape: "rect"` dùng tọa độ chuẩn hóa `0..1` trên khung hình clip (nửa trái: `x: 0.25, y: 0.5, w: 0.5, h: 1.0`; nửa phải: `x: 0.75, y: 0.5, w: 0.5, h: 1.0`). | `mask.js:8-52` |
| **Track / FX / Project Ops** | - `setProject` **CẤM** khóa `tracks`; `master` chỉ nhận `{gain}` (`-60..12` dB).<br>- `setTrack` cấu hình `A1`, `A2`... với `{gain, pan, out}`.<br>- `setFx` cấu hình chuỗi audio FX (`target: "track" \| "master" \| "clip"`).<br>- `relinkMedia` / `/library/...`: chấp nhận đường dẫn `/media/...` hoặc `/library/...`. | `project-ops.js:446, 506, 980, 1091-1138` |
| **Delivery Preset (`youtube-shorts`)** | Preset `youtube-shorts` đặt `1080x1920`, H.264 CRF 18, AAC 384k 48kHz nhưng **KHÔNG đặt `audio.loudness`**! Phải truyền tường minh `delivery: { preset: "youtube-shorts", audio: { loudness: -14, truePeak: -1 } }` khi `setProject` hoặc `fablecut_export`. | `delivery.js:176-181, 235-237` |

---

## 4. Kế hoạch thực thi 4 Pha chi tiết

### Pha 1 — Chuẩn hóa Schema, Presets & Fixtures mẫu (`fablecut-bundle`)
**Mục tiêu**: Khóa cứng hợp đồng dữ liệu đầu vào trước khi sửa adapter.

1. **Cập nhật `schema/input_schema.json`**:
   - Cho phép root fields: `schema_version`, `format`, `template_id` (enum 6 ID trong `presets/templates/index.json` khi có), `template_version`, `note`, `video_metadata`, `segments`.
   - `segments[].beat`: enum đầy đủ cho cả 6 template + legacy:
     - `hazard-rescue`: `EMERGENCY`, `DIAGNOSIS`, `TREATMENT`, `RELIEF`
     - `shock-hook`: `HOOK`, `REVEAL`, `PROOF`, `PAYOFF`
     - `how-it-works`: `QUESTION`, `STEP_1`, `STEP_2`, `STEP_3_RESULT` (và `STEP_*`)
     - `satisfying`: `SETUP`, `WORK`, `CLIMAX_SLOWMO`, `END`
     - `before-after`: `BEFORE`, `TRANSITION`, `AFTER`, `VERDICT`
     - `story`: `CHARACTER`, `PROBLEM`, `TURN`, `PAYOFF`
     - Legacy tương thích: `BUILD_UP`, `CLIMAX`
   - `segments[].text_overlay.position`: enum `["TOP_CENTER", "CENTER", "LOWER_THIRD"]`.
   - `segments[].text_overlay.style`: enum đầy đủ 14 key trong `presets/styles.json`.
   - `segments[].sfx_cue`: `type: ["object", "null"]` (hỗ trợ beat tĩnh không SFX ở `satisfying` / `story`).
   - `segments[].style`: cho phép object override per-video (`text_anim`, `preset_anim`, `transition_in`, `filter`, `sfx`, `motion`, `svg_overlay`, `split_screen`, `font_size`, `y`, v.v.).
   - Bảo toàn tính hợp lệ cho file legacy `examples/upload_snaptik.vn_7611044561959324946_commentary.capcut.json` (không chứa `template_id`, `time_range` có khoảng hở nhẹ ở Beat 1->2).
2. **Di chuyển & bổ sung 6 file mẫu `examples/irrigation-*.json`**:
   - Di chuyển 5 file từ `presets/video-templates-5/examples/irrigation-*.json` sang `examples/`, nâng cấp `"template_version": "1.1.0"`, giữ nguyên mốc 31.44s (`0-4.5`, `4.5-17.5`, `17.5-26`, `26-31.438367`) để so sánh công bằng.
   - Tạo mới `examples/irrigation-hazard-rescue.json` (`template_id: "hazard-rescue"`, `template_version: "1.1.0"`, 4 beats `EMERGENCY` -> `DIAGNOSIS` -> `TREATMENT` -> `RELIEF`).

---

### Pha 2 — Nâng cấp Engine Dựng Timeline Xác Định (`adapter/convert.py`)
**Mục tiêu**: Biến `convert.py` thành bộ biên dịch timeline hoàn chỉnh, loại bỏ toàn bộ lỗi runtime khi patch vào `FableCut`.

1. **Ưu tiên đọc template `v1.1.0` & kiểm soát hiệu ứng**:
   - Tìm `presets/templates/<id>.json` trước; chỉ fallback `presets/video-templates-5/templates/<id>.json` nếu không thấy.
   - Validate mọi `text_anim`, `preset_anim`, `transition_in`, `filter` (từ template hoặc override `segments[].style`) với danh sách `allowed_effects_only` và hằng số hợp lệ của `FableCut`. Nếu sai -> báo lỗi và thoát (`sys.exit(2)`), không sinh patch.
2. **Quản lý `project.json`, làm sạch timeline & tìm media thông minh**:
   - Đọc `fablecut-data/project.json`:
     - Sinh `removeClip` cho toàn bộ clip cũ **chưa bị lock** (bỏ qua track/clip đã lock trừ khi cờ ép).
     - Tái sử dụng `proj.media` nếu file `src` tồn tại trên đĩa; nếu thiếu, tìm theo `<video_id>`, `upload_<video_id>`, và fallback glob `*<video_id>*` trong `fablecut-data/media/` (giải quyết lệch tên `7611044561959324946` vs `snaptik.vn_7611044561959324946`).
     - Tự động tra cứu/đăng ký asset `/library/sfx/<id>.wav` và `/library/svg/<file>` (trùng khớp ID nếu đã có trong `proj.media`, hoặc sinh `addMedia` nếu chưa đăng ký).
3. **Sửa triệt để bug `lines 526-528` & Khóa an toàn Frame 0**:
   - Tách rõ 3 kênh từ `sfx_defaults[beat]` (kèm override ở `seg.get("style", {})`):
     - `text_anim` -> `text_clip["props"]["textAnim"]`
     - `preset_anim` -> op `applyPreset` (bỏ qua nếu `null` hoặc `"none"`)
     - `transition_in` -> `clip["transitionIn"] = {"type": t, "duration": 0.35}` (chỉ áp cho Beats 2 trở đi)
   - **Cưỡng chế Beat 1 (`idx == 0`) hiển thị ngay tại Frame 0**:
     - Ép `transitionIn` không đặt hoặc `"none"`.
     - Nếu `preset_anim` thuộc nhóm `IN` hoặc `OUT` -> loại bỏ hoặc đổi về `AT` an toàn (`pulse`/`shake` nếu phù hợp, hoặc bỏ `applyPreset`).
     - Nếu `props.textAnim` (kể cả kế thừa từ `presets/styles.json` như `word-pop`, `rise-mask`, `clip-reveal`, `word-slide`, `zoom-in`, `letter-pop`, `typewriter`) nằm trong nhóm ẩn ở `local = 0` -> tự động chuyển về `highlight` (hoặc `none`) trong danh sách Frame-0-visible (`none`, `highlight`, `karaoke`, `wave`, `bounce`, `shake`, `font-cut`).
4. **Safe-Box `900x1400` cho Text (`V2`)**:
   - Ánh xạ `text_overlay.position`:
     - `TOP_CENTER` -> `y = -420`
     - `CENTER` -> `style_cfg.get("y", 0)` (nếu không định nghĩa thì `0`, giữ các style như `HIGHLIGHT_YELLOW` `y=280..320` khi không ép đổi)
     - `LOWER_THIRD` -> `y = 420`
   - Đặt `boxW: 820`, `boxFit: true`, `vAlign: "middle"`, và **clamp `x`, `y`** theo `boxW`, `boxH` thực tế để 4 cạnh hộp chữ luôn nằm trong `[60, 960] x [120, 1600]`.
5. **Xây dựng `V1` Retention Sub-cuts, Motion, Grade, Speed & Split-Screen**:
   - Nếu một beat có thời lượng `> 5.0s` (trừ khi chế độ không cắt hoặc xử lý mượt liên tục hợp lý — với beat dài `> 5s` cắt các sub-clip `<= 5.0s` liền kề theo đúng mốc nguồn `in` tương ứng): luân phiên nhẹ scale/zoom (`1.0` -> `1.04`) hoặc keyframe chuyển động (`setKeys`) tạo nhịp biến đổi thị giác mỗi `<= 5s`.
   - Áp `props.filterPreset` theo `beat_fx["filter"]` (`cinematic`, `sunset`, `vintage`, `teal-orange`, `warm`, `pop`, v.v.).
   - Áp `motion`: `shake` (`props.shake`, `shakeSpeed: 8`), `zoom` (`scale` hoặc keyframe zoom mượt), `speed_ramp` (`props.speed` kẹp trong `[0.1, 8.0]`, điều chỉnh nguồn `in`/`duration` đúng tỉ lệ để không vượt quá độ dài file gốc!).
   - Hỗ trợ `before-after` (`split_screen: true`): trên beat `AFTER` (hoặc khi bật `split_screen`), tạo 2 lớp `V1` (`BEFORE` bên trái với `filterPreset: "vintage"`, `rect` mask `{x: 0.25, y: 0.5, w: 0.5, h: 1.0}`; `V2`/`V1b` `AFTER` bên phải với `filterPreset: "teal-orange"`, `rect` mask `{x: 0.75, y: 0.5, w: 0.5, h: 1.0}`) kèm 2 clip nhãn chữ nhỏ `BEFORE` / `AFTER` trong Safe-Box!
6. **Xây dựng `V3`/`V4` SVG Overlays & `A2` SFX Anti-Overlap + Audio Mix**:
   - **SVG (`V3`/`V4`)**: Nếu `svg_overlay` khác `null` (`step-1.svg`, `step-2.svg`, `step-3.svg`, `checkmark-success.svg`, `underline-swoosh.svg`), chèn clip `kind: "svg"` với `props.fit: "none"` và tọa độ an toàn trong `900x1400`.
   - **SFX (`A2`)**: Lấy cue từ `seg["sfx_cue"]` (nếu có) hoặc fallback `beat_fx["sfx"]` (trừ khi `seg["sfx_cue"] is None` và template quy định không SFX). Bảo vệ chống chồng lấn: nếu thời điểm `start + offset` cách cue trước `< 0.4s`, bỏ qua hoặc dịch sau `>= 0.4s`. Áp dụng gain tier cho `A2` (`gain: -6` đến `-9` dB).
   - **Audio Track & Delivery**:
     - `setTrack` cho `A1` (`gain: 0`) và `A2` (`gain: -6`).
     - `setFx` cho `A1` (chuỗi sạch thoại nhẹ hoặc preset `voice`/`podcast` nếu phù hợp) và `master` (limiter trần `-1.0 dB`).
     - `setProject` đặt `width: 1080, height: 1920, fps: 30`, `master: {gain: 0}`, và `delivery: {preset: "youtube-shorts", audio: {loudness: -14, truePeak: -1}}`.
7. **Tùy chọn tích hợp chạy thử**: Cập nhật `adapter/convert.py` hỗ trợ xuất file ops JSON (và tùy chọn `--export-spec` hoặc in lệnh `fablecut_export` chuẩn `youtube-shorts` + `-14 LUFS`).

---

### Pha 3 — Đồng bộ Backend & Web UI (`youtube-analyst-niches-forest`)
**Mục tiêu**: Đảm bảo từ bước Chặng 1 -> Chặng 2 -> TTS -> Export JSON sinh ra từ app web/API khớp 100% với `schema/input_schema.json` `v1.1.0`.

1. **`src/models/schemas.py`**:
   - Cập nhật `CommentarySegment.normalize_beat`: thêm `QUESTION`, `REVEAL`, `PROOF`, `TRANSITION`, `VERDICT`, `CHARACTER`.
   - Cập nhật `TextOverlay.normalize_style`: giữ nguyên/chuẩn hóa cả 14 style (`HIGHLIGHT_YELLOW`, `highlight-yellow`, `IMPACT_RED`, `BOLD_RED`, `CLEAN_WHITE`, `clean-white`, `NEON_GLOW`, `neon-glow`, `BOLD_CONTRAST`, `bold-contrast`, `HANDWRITTEN_WARM`, `handwritten-warm`, `CLEAN_CYAN`, `ELEGANT_GOLD`).
   - Cập nhật `CommentarySegment`: `sfx_cue: Optional[SFXCue] = None` và `style: Optional[dict] = None`.
   - Cập nhật `CapCutMetadata.template_version` mặc định thành `"1.1.0"`.
   - Cập nhật `CapCutCommentaryInterchange`: thêm tùy chọn `template_id: Optional[str] = None`, `template_version: Optional[str] = "1.1.0"`, `note: Optional[str] = None` (hoặc đồng bộ với `video_metadata`).
   - Cập nhật `CommentaryRequest` & `RewriteRequest`: thêm `template_id: Optional[str] = None`.
2. **`src/analyzer/commentary_engine.py`**:
   - Sửa `skill_to_template` dùng đúng ID trong `src/skills/registry.py`:
     - `"curiosity-explainer" -> "shock-hook"`
     - `"agri-practitioner" -> "how-it-works"`
     - `"satisfying-narrator" -> "satisfying"`
     - `"suspense-storyteller" -> "story"` (hoặc `"hazard-rescue"` khi timeline có tín hiệu khẩn cấp/sự cố)
     - `"witty-commentator" -> "shock-hook"`
   - Đọc đặc tả beat của `template_id` (từ `fablecut-bundle/presets/templates/`) để chèn vào `format_user_prompt`, giúp LLM sinh đúng tên `beat` theo template được chọn.
   - Ghi `"template_version": "1.1.0"` ở cả root và `video_metadata`.
3. **`src/skills/base.py` (+ 5 skill modules, giữ nguyên `len(registry) == 5`)**:
   - Hỗ trợ tham số tùy chọn `template_spec` / `template_id` trong `build_standard_user_prompt` & `format_user_prompt` để hướng dẫn LLM xuất đúng bộ beat, style mặc định và độ dài text overlay `<= 4-6` từ (không thêm skill mới vào `registry.py` để giữ test `len == 5`).
4. **`src/tts/tts_engine.py` (dòng 292)**:
   - Kẹp `actual_end` không vượt quá `total_duration` (trừ khi đoạn cuối thực sự dài hơn cần mở rộng có kiểm soát) và không tràn qua `start` của segment kế tiếp (hoặc đẩy liền mạch không để âm thanh đè lên nhau), giữ `time_range` nhất quán.
5. **`src/exporter/capcut.py` (dòng 166–173)**:
   - Mở rộng danh sách beat ưu tiên chọn frame cắt thumbnail cho đủ 6 template: `("CLIMAX", "CLIMAX_SLOWMO", "TREATMENT", "AFTER", "REVEAL", "TURN", "STEP_2", "RELIEF", "VERDICT", "PAYOFF", "HOOK", "EMERGENCY", "QUESTION", "BEFORE", "CHARACTER", "SETUP")`.
6. **`assets/sfx_library/catalog.json`**:
   - Thêm mục `"sfx_id": "soft_chime"` trỏ tới `ui_and_accents/soft_chime.wav`.
7. **`src/api/routes.py`**:
   - Thêm endpoint `GET /api/v1/templates` đọc từ `fablecut-bundle/presets/templates/index.json` (fallback danh sách tĩnh nếu không tìm thấy đường dẫn).
   - Truyền `request.template_id` vào `commentary_engine.generate_commentary(...)` ở cả `process_video` và `rewrite_commentary`.
   - Bổ sung gọi `cleanup_video_temp_files(...)` trong `rewrite_commentary`.
8. **`static/index.html` & `static/app.js`**:
   - Thêm `<select id="templateSelect">` (mặc định `Tự động theo Skill` + 6 template từ `/api/v1/templates`) và gửi `template_id` khi nhấn tạo/viết lại kịch bản.
   - Bọc guard `seg.sfx_cue ? ... : "NO SFX"` ở `static/app.js` dòng `391` và `416` để không văng lỗi khi `sfx_cue` là `null`.
9. **Kiểm thử backend**: Cập nhật/bổ sung unit test trong `tests/` và chạy `py -3.10 -m pytest -v`.

---

### Pha 4 — QA Automation, Skill Điều Phối, Render So Sánh 6 Bản & Vận Hành Lô
**Mục tiêu**: Khép kín quy trình bằng kiểm định tự động và nghiệm thu hình ảnh/âm thanh thực tế.

1. **Tạo `scripts/qa_check.py`**:
   - **Chế độ kiểm tra Input + Ops JSON**:
     - Validate `schema/input_schema.json`.
     - Kiểm tra `time_range` liên tục (chế độ strict cho video mới, cảnh báo ở legacy).
     - Kiểm tra ops sinh ra từ `convert.py`: Beat 1 `transitionIn` không phải hiệu ứng ẩn, `textAnim` Beat 1 thuộc nhóm Frame-0-visible, không dùng `IN`/`OUT` preset ở Beat 1, hộp chữ trong `900x1400`, `V1` không có clip `> 5s`, `A2` không có 2 SFX cách nhau `< 0.4s`, hiệu ứng nằm trong `allowed_effects_only`.
   - **Chế độ kiểm tra MP4 thành phẩm (sau `fablecut_export`)**:
     - `ffprobe`: xác nhận `1080x1920`, `yuv420p`, audio `aac 48kHz stereo`, độ dài khớp `duration_seconds` (`±0.5s`).
     - `ffmpeg -af ebur128=peak=true`: kiểm tra Integrated Loudness quanh `-14.0 LUFS` (`±1.5 LU`) và True Peak `<= -1.0 dBFS`.
2. **Triển khai Skill `shorts-orchestrator`**:
   - Đặt tại `.opencode/skills/shorts-orchestrator/SKILL.md` và `.agents/skills/shorts-orchestrator/SKILL.md`.
   - Chỉ mô tả quy trình điều phối (`validate` -> `convert.py` -> `fablecut_patch_project` -> `fablecut_frame` kiểm tra Frame 0 & các mốc giữa -> `fablecut_export` với `youtube-shorts` + `-14 LUFS` -> `qa_check.py`) và quy tắc bất biến (không chép code vào skill).
   - Thêm đúng 1 dòng con trỏ trong `AGENTS.md` dẫn tới `shorts-orchestrator`.
3. **Render so sánh 6 template (`examples/irrigation-*.json`)**:
   - Lần lượt chạy `convert.py` -> `fablecut_patch_project` -> `fablecut_frame(t=0)` -> `fablecut_export` (preset `youtube-shorts`, `delivery.audio: {loudness: -14, truePeak: -1}`) cho cả 6 bản:
     1. `irrigation-shock-hook.json`
     2. `irrigation-how-it-works.json`
     3. `irrigation-satisfying.json`
     4. `irrigation-before-after.json`
     5. `irrigation-story.json`
     6. `irrigation-hazard-rescue.json`
   - Chạy `scripts/qa_check.py` trên cả 6 file MP4 xuất ra, xem ảnh Frame 0 & frame đại diện, sau đó **chọn 3 template mặc định cho kênh**.
4. **Kiểm thử End-to-End 1 video hoàn chỉnh + Dọn dẹp**:
   - Chạy qua `youtube-analyst-niches-forest` -> sinh JSON + TTS + sync vào `fablecut-data/media/<video_id>/` -> `convert.py` -> `FableCut` render -> `qa_check.py`.
   - Chạy `cleanup.py --dry-run` và kiểm tra đối chiếu `CHECKLIST.md` (giữ nguyên cảnh báo `9Router` `0.0.0.0` / `JWT_SECRET`).

---

## 5. Ma trận Tiêu chí Nghiệm thu (Acceptance Gates)

| Gate | Công cụ kiểm tra | Điều kiện Đạt (PASS) |
|---|---|---|
| **G1. Schema & JSON** | `convert.py` / `qa_check.py` | 100% file `examples/*.json` (kể cả legacy) pass `schema/input_schema.json` |
| **G2. Frame 0 Visibility** | `qa_check.py` + `fablecut_frame(0)` | Beat 1 hiển thị rõ cả video `V1` lẫn tiêu đề `V2` ngay Frame 0 (`alpha = 1`, không bị clip/mask ẩn) |
| **G3. Safe-Box 9:16** | `qa_check.py` + inspect frame | Không có text box hay SVG vượt ra ngoài vùng `top>=120`, `bottom>=320`, `right>=120`, `left>=60` |
| **G4. Backend Pytest** | `py -3.10 -m pytest -v` | 100% unit/API tests trong `youtube-analyst-niches-forest` PASS, `len(skills) == 5` |
| **G5. Render & Loudness** | `fablecut_export` + `qa_check.py` | 6/6 bản `irrigation-*.mp4` đạt `1080x1920`, `-14.0 ± 1.5 LUFS`, True Peak `<= -1.0 dBFS` |
| **G6. Hygiene & Security** | `cleanup.py --dry-run` + `CHECKLIST.md` | `temp/` sạch, `exports/` & `library/` nguyên vẹn, `FableCut/` không có `git diff` |

---

## 6. Ghi chú rủi ro & Kiểm soát khi thực hiện tiếp

- **Tránh lặp lỗi cũ ở `convert.py`**: Khi tích hợp `/library/sfx/...` và `/library/svg/...`, kiểm tra kỹ định dạng `addMedia` trong `FableCut\project-ops.js` (`src` bắt đầu bằng `/media/` hoặc `/library/`, và server tự probe hoặc nhận metadata kích thước/duration chuẩn).
- **Tránh lỗi tốc độ `CLIMAX_SLOWMO` (`0.5x`)**: Khi đặt `props.speed = 0.5` cho đoạn 4s (`24..28s`), thời lượng nguồn tiêu thụ chỉ là `2.0s` (`in` phải khớp timeline và không vượt quá `media.duration`).
- **Tài nguyên `before-after` trên cùng 1 video stock**: Với video mẫu `irrigation-before-after.json` chỉ có 1 file MP4 đầu vào, nửa trái dùng đoạn `in = 0` (hoặc khung mở đầu) kèm filter `vintage`, nửa phải dùng đoạn `in = after_in` kèm filter `teal-orange` để thể hiện đối chiếu trực quan ngay cả khi chưa có 2 source riêng biệt.
- **Thứ tự thực hiện khuyến nghị ở phiên tiếp theo**: Pha 1 -> Pha 2 -> Pha 3 -> Pha 4 (làm dứt điểm từng pha và chạy kiểm thử ngay cuối mỗi pha).
