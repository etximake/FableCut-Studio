# AGENTS.md — FableCut-Studio Agent Harness

Monorepo xây dựng video ngắn dọc 9:16 qua 4 tầng tách biệt: phân tích (`youtube-analyst-niches-forest/`), lõi dựng video upstream (`FableCut/`), bộ biên dịch & kiểm định tất định (`fablecut-bundle/`), và dữ liệu runtime tách rời (`fablecut-data/`).

> **Nguyên lý kiến trúc Agent:**
> **Harness = Hướng dẫn + Công cụ + Môi trường + Trạng thái + Phản hồi.** Cả năm hệ thống phụ đều cần thiết và phải phối hợp chặt chẽ trong mọi tác vụ.

---

## 1. Hướng dẫn (Instructions — Ranh giới, Bất biến & Nguồn tri thức)

### Ranh giới thư mục & Bất biến (Invariants)
- **`FableCut/`** — Upstream FableCut v1.18.0 Node editor (`server.js`, `mcp-server.js`, `app.js`, zero npm dependencies). **Tuyệt đối không sửa các file lõi trong `FableCut/`** khi làm việc trên pipeline studio. Nếu được yêu cầu sửa riêng `FableCut/`, phải tuân thủ `FableCut/AGENTS.md` và `FableCut/CLAUDE.md`.
- **`fablecut-bundle/`** — Pipeline schema (`schema/input_schema.json`), presets (`presets/styles.json`, `presets/templates/`), compiler (`adapter/convert.py`), QA (`scripts/qa_check.py`), script quản lý server/cleanup, và cấu hình MCP (`opencode.json`, `antigravity.json`).
- **`youtube-analyst-niches-forest/`** — Dịch vụ Python FastAPI (`main.py`) có `.venv/` và `.env` riêng; trích xuất ảnh lưới 3x3 (contact sheets), sinh kịch bản bình luận JSON/SRT/voiceover, và xuất gói dữ liệu theo `video_id` sang `fablecut-data/media/<video_id>/`.
- **`fablecut-data/`** — Thư mục dữ liệu ngoài `FABLECUT_DATA_DIR` (`project.json`, `projects/`, `media/<video_id>/`, `exports/`, `analysis/`, `library/`). Dữ liệu runtime đã được gitignore; không ghi đè hoặc render lại các project/export hiện có trừ khi được yêu cầu rõ.
- **`docs/`** — Tài liệu hợp nhất (`docs/PIPELINE-QA.md`, `docs/HUONG-DAN-SU-DUNG.md`, `docs/PROJECT_MODELS.md`). Coi `docs/archive/` và `docs/design/` là tài liệu lịch sử tham khảo.

### Nguồn hướng dẫn chi tiết theo phân hệ
- `fablecut-bundle/AGENTS.md` — Quy trình cài đặt và vận hành 9Router + OpenCode + FableCut (Tiếng Việt).
- `FableCut/AGENTS.md` & `FableCut/CLAUDE.md` — Schema đầy đủ của FableCut, hợp đồng MCP tool, thuộc tính (props) và cơ chế compositor.
- `docs/PIPELINE-QA.md` — Danh mục kiểm tra (checklist) xác thực dữ liệu và QA bản render.
- `docs/PROJECT_MODELS.md` — Cấu hình ghim mô hình LLM theo từng chặng (Vision / Text).

---

## 2. Công cụ (Tools — CLI, Compiler, MCP & Bảo trì)

Chạy lệnh bên trong thư mục của từng phân hệ tương ứng (Windows / PowerShell).

### MCP & Bộ biên dịch (`fablecut-bundle/`)
- **Sửa timeline qua MCP**: Luôn dùng `fablecut_patch_project` thay vì ghi đè toàn bộ `project.json` khi chỉnh sửa từng phần. `fablecut-bundle/opencode.json` và `antigravity.json` định nghĩa stdio MCP server `fablecut` với `FABLECUT_DATA_DIR` trỏ về `fablecut-data/`.
- **Phạm vi của Compiler (`adapter/convert.py`)**: Chỉ phát sinh danh sách lệnh (`ops`), không bao giờ ghi trực tiếp vào `project.json`. Lệnh dọn dẹp tự động chỉ xóa các clip có tiền tố `fcpipe_` (giữ nguyên các clip do người dùng tạo hoặc đã khóa). Chỉ sử dụng các preset/template có sẵn trong `fablecut-bundle/presets/`, không tự bịa tên hiệu ứng hay style mới.

```powershell
# Biên dịch kịch bản JSON sang danh sách lệnh ops (luôn xuất file tạm ra $env:TEMP)
py -3.10 adapter/convert.py --json examples/<file>.json --output "$env:TEMP\out.ops.json"
```

### Quản lý FableCut Server (`fablecut-bundle/`)
Luôn khởi động qua `server.bat` để `FABLECUT_DATA_DIR` trỏ đúng vào `fablecut-data/` (chạy trực tiếp `node server.js` trong `FableCut/` sẽ làm sai lệch thư mục dữ liệu về `FableCut/`):

```powershell
.\server.bat start      # Khởi động FableCut tại http://localhost:7777
.\server.bat status     # Kiểm tra PID trên cổng 7777
.\server.bat stop       # Dừng server trên cổng 7777
.\server.bat restart    # Khởi động lại server
```

### Dịch vụ Phân tích Video (`youtube-analyst-niches-forest/`)
Luôn sử dụng môi trường ảo `.venv` của phân hệ này:

```powershell
.\run.bat                                                       # Khởi động FastAPI server (main.py)
```

### Dọn dẹp an toàn (`fablecut-bundle/`)
```powershell
.\cleanup.bat preview                     # Chạy thử (dry-run): hiển thị các mục temp/ và media/ có thể dọn
```

---

## 3. Môi trường (Environment — Runtime, Cổng dịch vụ & Bảo mật)

- **Python Runtime tách biệt**:
  - Tại `fablecut-bundle/`: Bắt buộc dùng `py -3.10` (`tests/test_pipeline_qa.py` gọi cứng `py -3.10`, và `convert.py` / `qa_check.py` yêu cầu thư viện `jsonschema` không có fallback).
  - Tại `youtube-analyst-niches-forest/`: Bắt buộc dùng `.\.venv\Scripts\python.exe`.
- **Node.js Runtime (`FableCut/`)**: Yêu cầu Node >= 18, không cần `npm install` (sử dụng `node:test` tích hợp sẵn).
- **Cơ chế nạp cấu hình Analyst**: `youtube-analyst-niches-forest/src/core/config.py` (`DynamicSettings`) đọc lại `.env` qua `dotenv_values` ở mỗi lần truy xuất, ghi đè `os.environ` nếu khóa tồn tại trong `.env`. Khi chạy pytest, `tests/conftest.py` tự động cô lập `EXPORTS_DIR` và `TEMP_DIR`.
- **Cờ môi trường Windows cho FableCut**: Các bài test Node tùy chỉnh khi khởi tạo `server.js` hoặc `mcp-server.js` trên thư mục tạm phải đặt `FABLECUT_NO_FS_WATCH=1` (tránh lỗi libuv abort trên Windows khi theo dõi thư mục tạm) và `FABLECUT_NO_AUTOSTART=1` (ngăn tiến trình `server.js` chạy ngầm mồ côi).
- **Bảo mật & 9Router**: Tuyệt đối không ghi API key thật vào bất kỳ file nào; `9Router` (`http://localhost:20128/v1`) đọc `{env:ROUTER_API_KEY}` và chỉ dùng API key trực tiếp từ nhà cung cấp (không dùng OAuth của gói đăng ký). Không tự ý thay đổi cấu hình bảo mật hay địa chỉ bind (`127.0.0.1`) của `9Router` nếu không được yêu cầu.

---

## 4. Trạng thái (State — Dữ liệu bền vững, Fixtures & Cô lập)

- **Trạng thái dự án & Tài sản (`fablecut-data/`)**:
  - Chứa trạng thái timeline hiện hành (`project.json`), các dự án lưu trữ (`projects/`), tài nguyên đầu vào (`media/<video_id>/`), thư viện dùng chung (`library/fonts/`, `library/sfx/`), và sản phẩm đầu ra (`exports/`).
  - `cleanup.py` tự động bảo vệ `fablecut-data/exports/`, `library/`, `projects/`, và mọi tệp media đang được tham chiếu trong `fablecut-data/project.json`.
- **Bảo vệ trạng thái Clip người dùng**: Khi cập nhật timeline, chỉ các clip mang tiền tố `fcpipe_` thuộc quyền quản lý của trình biên dịch; các clip khác và clip đã khóa (`locked`) phải được bảo toàn.
- **Fixtures chỉ đọc (`fablecut-bundle/examples/`)**: Tuyệt đối không ghi file `.ops.json` sinh ra hoặc kết quả test vào `fablecut-bundle/examples/`; mọi đầu ra trung gian phải ghi vào `$env:TEMP`.

---

## 5. Phản hồi (Feedback — Kiểm định QA, Test Suites & Thị giác thực tế)

Mọi thay đổi hoặc bước sinh dữ liệu phải được xác minh qua các vòng phản hồi tự động và trực quan trước khi kết luận hoàn thành.

### Kiểm định Pipeline & QA (`fablecut-bundle/`)
```powershell
py -3.10 -m pytest -q                                           # Chạy toàn bộ test pipeline
py -3.10 -m pytest tests/test_pipeline_qa.py -k <test_name>     # Chạy một test cụ thể
py -3.10 scripts/qa_check.py --all-examples                     # Kiểm tra tất cả fixtures + font .woff2 trong fablecut-data/library/fonts/
py -3.10 scripts/qa_check.py --input examples/<file>.json --ops "$env:TEMP\out.ops.json"
py -3.10 scripts/qa_check.py --render <path.mp4> --duration <seconds>   # Kiểm tra file MP4 xuất ra (cần ffmpeg + ffprobe)
```

### Kiểm thử Dịch vụ Phân tích (`youtube-analyst-niches-forest/`)
```powershell
.\.venv\Scripts\python.exe -m pytest -q                         # Chạy toàn bộ 24 bài test backend
.\.venv\Scripts\python.exe -m pytest tests/<file>.py -k <name>  # Chạy một bài test cụ thể
```

### Kiểm thử Lõi FableCut (`FableCut/`)
```powershell
npm test                                  # Chạy toàn bộ bộ test FableCut
node --test test/<file>.test.js           # Chạy một file test cụ thể
```

### Phản hồi thị giác thực tế (QA vs Visual Truth)
- Việc vượt qua `qa_check.py --input --ops` mới chỉ xác nhận tính hợp lệ về cấu trúc/schema, **không** đảm bảo hiển thị thực tế tại Frame 0, lề vùng an toàn (safe-box margins), lớp phủ (overlays) hay bản phối âm thanh cuối cùng.
- Bắt buộc kiểm tra khung hình được render thực tế (qua công cụ `fablecut_frame` hoặc file video xuất ra) trước khi đánh dấu một template hoặc video là đã hoàn tất xác minh.

