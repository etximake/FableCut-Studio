# Model đã ghim — FableCut Pipeline

## Chặng 1 — Vision & Phân tích kịch bản
- Model vision/tool-calling được xác nhận có mặt trên 9Router: `ag/gemini-4-argon-high` (endpoint `/v1/models`, 2026-11-12). Chưa thực hiện benchmark độc lập trên contact sheet trong phiên này; xem đây là model khả dụng, không phải lựa chọn đã đánh giá chất lượng.
- Yêu cầu đầu ra: Cung cấp file JSON cấu trúc `segments`, `time_range`, `text_overlay`, `voiceover`.

## Chặng 2 — Text & Timeline Generation
- Model text đã kiểm chứng cho generation thực tế: chưa ghim; không tự suy ra từ danh sách model.
- Adapter chuyển đổi: `adapter/convert.py` validate JSON schema và sinh payload `fablecut_patch_project`.

## Chặng 3 — MCP Video Editor & Render Engine
- Engine: FableCut v1.18.0 (Local MCP Stdio)
- Data Dir: `D:\HOANG HA\Deverlopper Software\fablecut-data`
- Export Preset: `youtube-shorts` (1080x1920 @ 30fps)
- Kết quả render lịch sử: MP4 hiện hữu 31.438s (không render lại). Các test pipeline đã chạy ngày 2026-11-12; lần này không gọi MCP để patch timeline hoặc render.
