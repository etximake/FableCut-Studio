# 04. ĐẶC TẢ API & CAPCUT JSON SCHEMA (CAPCUT INTERCHANGE & API)

## 1. CAPCUT INTERCHANGE JSON SCHEMA (VERSION 3)

Đây là hợp đồng dữ liệu chuẩn đầu ra giữa hệ thống backend và các công cụ biên tập (CapCut Desktop, Premiere, CapCut HUD). Schema v3 được tối ưu cho **lời bình mượt mà liên tục** trên 1 video ngắn 40–50s:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CapCutCommentaryInterchangeV3",
  "type": "object",
  "required": [
    "schema_version",
    "format",
    "video_metadata",
    "segments"
  ],
  "properties": {
    "schema_version": { "type": "integer", "const": 3 },
    "format": { "type": "string", "const": "youtube-story-commentary-capcut" },
    "video_metadata": {
      "type": "object",
      "required": ["video_id", "title", "duration_seconds", "skill_applied", "language", "total_words", "average_wpm"],
      "properties": {
        "video_id": { "type": "string" },
        "title": { "type": "string" },
        "duration_seconds": { "type": "number" },
        "skill_applied": { "type": "string", "enum": ["curiosity-explainer", "suspense-storyteller", "satisfying-narrator", "witty-commentator"] },
        "language": { "type": "string", "enum": ["vi", "en"] },
        "total_words": { "type": "integer" },
        "average_wpm": { "type": "number" }
      }
    },
    "segments": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["beat", "time_range", "voiceover", "text_overlay", "sfx_cue", "visual_hint"],
        "properties": {
          "beat": { "type": "string", "enum": ["HOOK", "BUILD_UP", "CLIMAX", "PAYOFF"] },
          "time_range": {
            "type": "object",
            "required": ["start", "end"],
            "properties": {
              "start": { "type": "number" },
              "end": { "type": "number" }
            }
          },
          "voiceover": { "type": "string" },
          "text_overlay": {
            "type": "object",
            "required": ["text", "position", "style"],
            "properties": {
              "text": { "type": "string" },
              "position": { "type": "string", "enum": ["TOP_CENTER", "CENTER", "LOWER_THIRD"] },
              "style": { "type": "string", "enum": ["HIGHLIGHT_YELLOW", "BOLD_RED", "CLEAN_WHITE"] }
            }
          },
          "sfx_cue": {
            "type": "object",
            "required": ["suggested_sfx", "start_offset", "volume"],
            "properties": {
              "suggested_sfx": { "type": "string" },
              "start_offset": { "type": "number" },
              "volume": { "type": "number" }
            }
          },
          "visual_hint": { "type": "string" }
        }
      }
    }
  }
}
```

---

## 2. DANH SÁCH RESTFUL API ENDPOINTS

Base URL: `/api/v1`

| Method | Endpoint | Mô tả chức năng |
| :--- | :--- | :--- |
| `POST` | `/commentary/process-video` | Tải lên file video hoặc URL $\rightarrow$ chạy Preprocessor $\rightarrow$ Chặng 1 $\rightarrow$ Chặng 2 $\rightarrow$ trả về CapCut JSON. |
| `POST` | `/commentary/rewrite` | Viết lại lời bình với Skill khác dựa trên Timeline thị giác có sẵn (chỉ tốn ~400 text tokens, không đọc lại ảnh). |
| `GET` | `/commentary/{video_id}/export` | Xuất và tải về file `.capcut.json` hoặc file phụ đề `.srt`. |
| `GET` | `/skills` | Lấy danh sách các Persona biên kịch đang được kích hoạt trong hệ thống. |
| `GET` | `/sfx/catalog` | Lấy danh mục hiệu ứng âm thanh mẫu có sẵn trong thư viện. |
| `GET` | `/ai/status` | Kiểm tra tình trạng kết nối API của mô hình Vision và Text. |

---

## 3. CHI TIẾT CÁC ENDPOINT QUAN TRỌNG

### 3.1. Xử lý Video Toàn Diện: `POST /api/v1/commentary/process-video`
Endpoint này tiếp nhận file video hoặc link YouTube/TikTok:

* **Request (Multipart Form hoặc JSON):**
```json
{
  "video_url": "https://www.youtube.com/shorts/dQw4w9WgXcQ",
  "skill_id": "curiosity-explainer",
  "language": "vi",
  "target_duration": 45.0
}
```

* **Quy trình xử lý nội bộ:**
  1. Nếu là URL: Tải video nhanh bằng `yt-dlp`.
  2. Kích hoạt `LocalVideoPreprocessor`: Tạo Contact Sheet 3x3 và lọc âm thanh VAD.
  3. Kích hoạt Chặng 1: Gửi 1 ảnh lưới lên Vision LLM $\rightarrow$ lưu `Visual Action Timeline` vào DB.
  4. Kích hoạt Chặng 2: Gửi Timeline vào Text LLM theo `skill_id` $\rightarrow$ sinh lời bình và gắn nhãn SFX.
  5. Đóng gói và trả về JSON chuẩn Schema v3.

* **Response (200 OK):**
```json
{
  "status": "SUCCESS",
  "video_id": "vid_2026_test",
  "capcut_json": {
    "schema_version": 3,
    "format": "youtube-story-commentary-capcut",
    "video_metadata": {
      "video_id": "vid_2026_test",
      "title": "Nước sôi ở nhiệt độ phòng",
      "duration_seconds": 45.0,
      "skill_applied": "curiosity-explainer",
      "language": "vi",
      "total_words": 94,
      "average_wpm": 125.3
    },
    "segments": [
      {
        "beat": "HOOK",
        "time_range": { "start": 0.0, "end": 4.5 },
        "voiceover": "Bạn có tin nước có thể sôi sùng sục ngay ở nhiệt độ phòng mà không cần lửa?",
        "text_overlay": {
          "text": "NƯỚC SÔI KHÔNG CẦN LỬA?",
          "position": "TOP_CENTER",
          "style": "HIGHLIGHT_YELLOW"
        },
        "sfx_cue": {
          "suggested_sfx": "cinematic_sub_boom",
          "start_offset": 0.1,
          "volume": 0.85
        },
        "visual_hint": "Giữ nguyên bình thủy tinh, zoom nhẹ 5% vào bề mặt nước"
      }
    ]
  },
  "token_usage": {
    "stage1_vision_tokens": 1050,
    "stage2_text_tokens": 420,
    "total_tokens": 1470
  }
}
```

---

### 3.2. Viết Lại Lời Bình (Zero Vision Token Cost): `POST /api/v1/commentary/rewrite`
Dành cho tình huống người dùng muốn đổi giọng điệu hoặc ngôn ngữ mà không tốn lại tiền đọc ảnh:

* **Request:**
```json
{
  "video_id": "vid_2026_test",
  "new_skill_id": "witty-commentator",
  "language": "vi"
}
```

* **Response:**
Trả về ngay kịch bản mới với tốc độ < 1 giây và chỉ tiêu tốn đúng ~400 tokens văn bản!

---

## 4. TÍCH HỢP VỚI CAPCUT HUD VÀ CAPCUT DESKTOP

File JSON v3 xuất ra tương thích hoàn toàn với công cụ **CapCut Story HUD** (đã xây dựng trong dự án trước):
1. **1-Click Copy:** Editor bấm nút trên giao diện HUD nổi để copy từng câu Voiceover và dán vào tính năng *Text-to-Speech* của CapCut PC.
2. **SFX Drag-and-Drop:** Tự động chỉ rõ tên file âm thanh tương ứng trong thư mục `assets/sfx_library/` để kéo vào timeline.
3. **Phụ đề tự động:** Xuất kèm file `.srt` với thời gian khớp từng mili-giây để CapCut tự sinh phụ đề chạy trên màn hình.
