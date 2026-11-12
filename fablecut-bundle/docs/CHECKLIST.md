# Checklist buổi test đầu tiên

- [ ] 9Router ở bản 0.4.44 trở lên, đã đặt JWT_SECRET riêng, chỉ bind 127.0.0.1 *(Cảnh báo: Hiện đang bind 0.0.0.0)*
- [x] `curl http://localhost:20128/v1/models` trả về danh sách model
- [x] Đã clone đúng link: https://github.com/ronak-create/FableCut (owner ronak-create)
- [x] Thư mục dự án đã có AGENTS.md, opencode.json, antigravity.json, PROJECT_MODELS.md
- [x] FABLECUT_DATA_DIR đặt ngoài thư mục repo FableCut (`D:\HOANG HA\Deverlopper Software\fablecut-data`)
- [ ] Agent đã thực hiện xong các bước theo AGENTS.md và báo cáo đầy đủ (chưa chạy MCP patch/render trong phiên xác minh code)
- [x] Model kết nối qua cổng 9Router
- [ ] `fablecut_status` chạy được, editor mở tại http://localhost:7777 (chưa kiểm tra trong phiên này)
- [x] Đã có render irrigation 31,438s; giữ nguyên asset rev 41, không re-render trong phiên này
- [ ] Pass validate JSON schema + render đúng mốc 1080x1920 (schema, ops, tests pass; render mới chưa thực hiện)

Nếu một ô chưa tick được, dừng ở ô đó, chụp lỗi gửi cho Muse, đừng cố chạy tiếp.
