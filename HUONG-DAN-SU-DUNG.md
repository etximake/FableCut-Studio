# HƯỚNG DẪN SỬ DỤNG VÀ VẬN HÀNH FABLECUT BUNDLE

> **Hệ thống**: Pipeline dựng và render video ngắn dọc 9:16 tự động  
> **Kiến trúc**: `Tool tạo kịch bản/âm thanh` ➔ `Adapter (Schema + Presets)` ➔ `FableCut Engine (MCP/REST)` ➔ `Video Shorts 9:16`

---

## I. TỔNG QUAN KIẾN TRÚC & THƯ MỤC

Ghi chú kiểm chứng người xem cho project irrigation rev 41: [`VIEWER-VIDEO-LIMITATIONS.md`](fablecut-bundle/docs/VIEWER-VIDEO-LIMITATIONS.md). Tài liệu chỉ mô tả render hiện có; không chỉnh project hoặc render lại.

Hệ thống được tổ chức theo nguyên tắc **tách bạch 4 thành phần** để an toàn dữ liệu, gom gọn file theo từng video và dễ dàng dọn dẹp theo lô (10–20 video):

```text
D:\HOANG HA\Deverlopper Software\FableCut-Studio\
├── youtube-analyst-niches-forest/  # [Lớp 0 - PHÂN TÍCH & KỊCH BẢN]: Tạo JSON, SRT, voiceover, 3x3 sheet
│   └── temp/                       # File tải tạm/trung gian (tự động dọn ngay sau khi export)
├── FableCut/                       # [Lớp 1 - ENGINE]: Repo mã nguồn mở FableCut (giữ nguyên gốc)
├── fablecut-data/                  # [Lớp 2 - DATA]: Dữ liệu tách ngoài repo FableCut
│   ├── media/<video_id>/           # Thư mục riêng cho từng video (7 file đồng bộ từ Analyst)
│   ├── exports/                    # Video thành phẩm sau render 9:16 (ĐƯỢC BẢO VỆ KHI DỌN)
│   ├── library/                    # Kho SFX, fonts, elements, SVG dùng chung (ĐƯỢC BẢO VỆ)
│   ├── projects/                   # Lưu trữ các project của FableCut (quản lý bằng Archive/Delete)
│   ├── analysis/                   # Cache proxy & frame tạm (có thể dọn an toàn)
│   └── project.json                # Project đang mở trong FableCut
└── fablecut-bundle/                # [Lớp 3 - CHẤT XÁM & ADAPTER]: Thư mục dự án này
    ├── server.bat                  # Script bật / tắt / kiểm tra FableCut server (menu hoặc CLI)
    ├── cleanup.bat                 # Script nhấp đúp mở menu / chạy nhanh dọn dẹp theo lô
    ├── cleanup.py                  # Lõi script dọn dẹp an toàn theo lô 10–20 video
    ├── adapter/
    │   ├── convert.py              # Bộ chuyển đổi JSON -> ops & tự động đăng ký media/<video_id>/
    │   └── final_patch_ops.json
    ├── presets/
    │   └── styles.json             # Thư viện preset giao diện chữ, font, hiệu ứng
    ├── schema/
    │   └── input_schema.json       # Bộ kiểm duyệt tính hợp lệ của kịch bản JSON
    ├── examples/                   # Bộ dữ liệu mẫu (video stock, audio wav, json kịch bản)
    ├── antigravity.json            # Cấu hình kết nối MCP cho Antigravity
    ├── opencode.json               # Cấu hình kết nối MCP cho OpenCode
    └── fablecut-bundle/docs/       # Tài liệu, checklist và nhật ký model
        ├── PROJECT_MODELS.md
        ├── CHECKLIST.md
        └── VIEWER-VIDEO-LIMITATIONS.md
```

---

## II. CẤU TRÚC FILE THEO TỪNG VIDEO (`media/<video_id>/`)

Khi bạn chạy xong một video trên `youtube-analyst-niches-forest`, toàn bộ tài nguyên đầu vào cho FableCut được xuất gọn vào **1 thư mục con duy nhất** theo `video_id`:

`D:\HOANG HA\Deverlopper Software\FableCut-Studio\fablecut-data\media\<video_id>\`

Bên trong thư mục này gồm tối đa 7 file đồng bộ:
1. **Video Stock (`.mp4`)**: `<video_id>.mp4`
2. **Giọng đọc Voiceover (`.wav`/`.mp3`)**: `<video_id>_voiceover.wav`
3. **Kịch bản Timeline (`.json`)**: `<video_id>_commentary.capcut.json` (chứa `segments`, `time_range`, `text_overlay`, `sfx_cue`)
4. **Phụ đề SRT (`.srt`)**: `<video_id>_subtitles.srt` và `<video_id>_subtitles_vi.srt`
5. **Ảnh kiểm tra & Thumbnail (`.jpg`)**: `<video_id>_contact_sheet_3x3.jpg` và `<video_id>_thumbnail.jpg`

> **Lưu ý về file tạm**: Các file tải về thô, ảnh 3x3 tạm và từng đoạn audio `_seg_*.wav` trong `youtube-analyst-niches-forest/temp/` được hệ thống **tự động xóa ngay sau khi export xong** sang `fablecut-data/media/<video_id>/` (trừ file ngoài `temp/` do người dùng trỏ trực tiếp).

---

## III. CƠ CHẾ LƯU DỰ ÁN & KHI NÀO BẮT ĐẦU DỰ ÁN MỚI

### 1. Vì sao mở lại Server vẫn thấy dự án cũ? (Tính năng Persistent Project)
Khi bạn bật `server.bat` và mở `http://localhost:7777`, FableCut luôn hiển thị dự án gần nhất. **Đây là tính năng được thiết kế sẵn, không phải lỗi**:
- **Lưu bền vững (`fablecut-data/project.json`)**: Toàn bộ trạng thái timeline đang làm việc được lưu trực tiếp tại `D:\HOANG HA\Deverlopper Software\FableCut-Studio\fablecut-data\project.json`. Nhờ đó bạn tắt máy, đóng trình duyệt hay khởi động lại server đều không bị mất việc.
- **Đồng bộ thời gian thực (Live-Reload)**: Cả trình duyệt (`localhost:7777`), AI Agent (qua MCP) và script `adapter/convert.py` đều cùng đọc/ghi vào dự án đang mở này. Agent sửa xong là trình duyệt tự cập nhật ngay lập tức.
- **Kho lưu trữ nhiều dự án (`fablecut-data/projects/<id>/`)**: Khi bạn tạo dự án mới hoặc chuyển sang dự án khác, dự án cũ không bị mất mà được cất tự động vào thư mục `fablecut-data/projects/<id>/` để mở lại bất cứ lúc nào.

### 2. Có dự án mới thì bắt đầu từ đâu? (`youtube-analyst` hay `fablecut-bundle`?)
Tùy vào nguyên liệu bạn đang có, hãy chọn 1 trong 2 lộ trình:

| Tình huống của bạn | Nơi bắt đầu | Quy trình thực hiện |
|---|---|---|
| **Trường hợp A**: Chỉ mới có link video hoặc file video thô (chưa có kịch bản, chưa có file giọng đọc AI, chưa chia mốc giây) | **`youtube-analyst-niches-forest`** | 1. Chạy phân tích trên `youtube-analyst-niches-forest` để sinh trọn bộ 7 file vào `fablecut-data/media/<video_id>/`.<br>2. Sang `fablecut-bundle`, nhắn Agent dựng & xuất video `<video_id>`. |
| **Trường hợp B**: Đã có sẵn bộ file (`video` + `voiceover` + `.capcut.json`) hoặc muốn tự dựng/cắt ghép thủ công từ đầu | **`fablecut-bundle`** *(Bỏ qua `youtube-analyst`)* | - **Tự động**: Nhắn Agent hoặc chạy `adapter/convert.py` trỏ vào file JSON/media có sẵn.<br>- **Thủ công**: Mở `http://localhost:7777` ➔ **Projects** ➔ **New Project** (chọn khung `Vertical 9:16`) và kéo thả file vào dựng. |

---

## IV. HƯỚNG DẪN CHI TIẾT SỬ DỤNG AI AGENT (CHAT TRONG OPENCODE / ANTIGRAVITY)

> **💡 "AI Agent" là gì và mở ở đâu?**
> - **AI Agent chính là khung chat trong phần mềm OpenCode (hoặc Antigravity)** khi bạn mở tại thư mục dự án `D:\HOANG HA\Deverlopper Software\FableCut-Studio\fablecut-bundle`.
> - Nhờ 2 file cấu hình `opencode.json` và `antigravity.json` nằm sẵn trong thư mục này, ngay khi bạn mở OpenCode / Antigravity lên và chat, AI đã được gắn sẵn bộ công cụ **MCP FableCut** (có khả năng đọc/sửa timeline, thêm media, chỉnh âm thanh và bấm nút render hộ bạn).
> - **Cách mở**: Mở Terminal / PowerShell tại thư mục `fablecut-bundle` rồi gõ `opencode` (hoặc `antigravity`), hoặc mở thư mục `fablecut-bundle` trong ứng dụng OpenCode / Antigravity Desktop rồi gõ yêu cầu vào ô chat.

### Bước 1: Khởi động hoặc Dừng Server FableCut (`server.bat`)
Trước khi làm việc hoặc xem preview, đảm bảo FableCut Server đang chạy ở cổng `7777`:

- **Cách 1 (Nhấp đúp chuột vào `server.bat`)**:
  ```text
  [1] Start Server   (Bật server ngầm & mở trình duyệt 7777)
  [2] Stop Server    (Tắt server an toàn & giải phóng cổng 7777)
  [3] Restart Server (Khởi động lại)
  [4] Check Status   (Kiểm tra trạng thái đang Bật hay Tắt)
  [5] Open Editor    (Mở nhanh giao diện web)
  ```
- **Cách 2 (Dòng lệnh CLI)**:
  ```powershell
  .\server.bat start    # Bật server chạy ngầm & mở web
  .\server.bat stop     # Tắt server
  .\server.bat status   # Xem server đang chạy hay tắt (kèm PID)
  .\server.bat restart  # Khởi động lại server
  ```

---

### Bước 2: Các mẫu câu lệnh (Prompt) giao việc cho Agent

#### A. Dựng và render một video mới từ đầu (Pipeline tự động)
Khi thư mục `fablecut-data/media/<video_id>/` đã có đủ file từ `youtube-analyst`, bạn chỉ cần nhắn:
> *"Hãy dựng và render Short 9:16 cho video `<video_id>` trong `D:\HOANG HA\Deverlopper Software\FableCut-Studio\fablecut-data\media\<video_id>\`."*

Hoặc nếu muốn chọn sẵn template nhịp điệu (`shock-hook`, `how-it-works`, `satisfying`, `story`, `before-after`, `hazard-rescue`):
> *"Dựng video `<video_id>` theo template `shock-hook`, kiểm tra timeline rồi xuất bản 9:16."*

**Những gì Agent sẽ tự động làm ngầm cho bạn:**
1. Chạy `adapter/convert.py` để kiểm duyệt kịch bản JSON theo `schema/input_schema.json`.
2. Tự động quét thư mục `fablecut-data/media/<video_id>/`, dùng `ffprobe` đo thông số kỹ thuật và sinh lệnh `addMedia` / `relinkMedia` với đường dẫn `/media/<video_id>/...` (không nhân bản file rác ra ngoài).
3. Gọi công cụ MCP `fablecut_patch_project` để dựng toàn bộ các lớp lên Timeline (Video nền `V1`, hiệu ứng/overlay, chữ `V2`, giọng đọc `A1`, tiếng động SFX `A2`).
4. Gọi `fablecut_export` để xuất file `.mp4` chuẩn 1080x1920 vào `fablecut-data/exports/`.

#### B. Quản lý Dự án (Tạo mới, Chuyển đổi, Lưu trữ dự án cũ)
Bạn có thể bảo Agent quản lý danh sách project mà không cần tự bấm trên web:
- **Xem danh sách các dự án đang có**:
  > *"Liệt kê các project hiện có trong FableCut và cho biết project nào đang mở."*
- **Tạo một dự án 9:16 trắng hoàn toàn mới**:
  > *"Tạo cho tôi một project mới khung dọc 9:16 (1080x1920, 30fps) đặt tên là `Test Video Moi` và mở nó lên."*
- **Mở lại một dự án cũ để sửa tiếp**:
  > *"Mở lại project `<tên hoặc id project cũ>` để tôi chỉnh sửa tiếp."*
- **Nhân bản (Duplicate) dự án đang mở để thử nghiệm phương án khác**:
  > *"Nhân bản project hiện tại thành một bản copy để tôi thử đổi style chữ khác."*

#### C. Ra lệnh cho Agent chỉnh sửa Timeline đang mở
Sau khi dựng xong và xem trên `http://localhost:7777`, nếu muốn sửa bất kỳ chi tiết nào, bạn chỉ cần nhắn trực tiếp cho Agent. Agent sẽ dùng `fablecut_patch_project` để sửa đúng phần đó (không làm hỏng các phần khác):

- **Sửa nội dung câu chữ (Text Overlay)**:
  > *"Ở đoạn chữ thứ 2 (từ 4.5s đến 17.5s), hãy đổi nội dung chữ thành: `WATERING AN ENTIRE HILLSIDE AT ONCE!`"*
- **Đổi phong cách chữ (Style Preset)**:
  > *"Đổi đoạn chữ đầu tiên (Hook) sang style `IMPACT_RED`, các đoạn còn lại dùng style `HIGHLIGHT_YELLOW`."*
- **Chỉnh vị trí, kích thước chữ (tránh che chủ thể hoặc giao diện TikTok/Shorts)**:
  > *"Cho tất cả các dòng chữ hạ thấp xuống một chút (tăng tọa độ `y` xuống khoảng 420) và giảm cỡ chữ xuống 68."*
- **Chỉnh âm thanh, giọng đọc & tiếng động (Audio / SFX)**:
  > *"Chuẩn hóa âm lượng (normalize) giọng đọc về mức -14 LUFS và giảm âm lượng các tiếng SFX xuống một nửa."*
  > *"Khử nhiễu (denoise) mức vừa cho track giọng đọc."*
- **Dịch chuyển hoặc cắt ghép mốc thời gian**:
  > *"Rút ngắn đoạn mở đầu xuống còn 0 đến 3.5 giây, và đẩy đoạn thứ 2 lên bắt đầu từ 3.5 giây."*
- **Xuất lại video sau khi đã chỉnh sửa ưng ý**:
  > *"Tôi đã xem preview thấy ổn rồi, hãy export dự án hiện tại ra file MP4 9:16 vào thư mục exports."*

---

## V. BA CÁCH CHỈNH SỬA DỰ ÁN (KẾT HỢP LINH HOẠT)

Khi cần chỉnh sửa một dự án, bạn không bị bó buộc vào một cách duy nhất mà có thể kết hợp cả **3 cách** dưới đây (chúng tự động đồng bộ với nhau qua `project.json`):

### Cách 1: Chỉnh sửa bằng chuột trên Giao diện Web (`http://localhost:7777`)
*Phù hợp nhất khi bạn muốn vừa nhìn mắt, vừa nghe tai, vừa kéo thả tinh chỉnh từng khung hình:*
1. Mở trình duyệt tại `http://localhost:7777`.
2. Trên Timeline, bạn sẽ thấy rõ các lớp:
   - **Track V2 (Text / Overlays)**: Nhấp vào từng khối chữ để gõ lại nội dung, đổi font, đổi màu, kéo khung chữ lên/xuống trực tiếp trên màn hình xem trước.
   - **Track V1 (Video nền)**: Kéo mép clip để cắt đầu/cuối, chỉnh độ phóng (`scale`), vị trí (`x`, `y`) hoặc độ mờ.
   - **Track A1 / A2 (Voiceover & SFX)**: Kéo thanh âm lượng, dịch vị trí tiếng động cho khớp đúng nhịp hình.
3. **Tự động lưu**: Mọi thao tác bạn kéo trên web đều được lưu ngay vào `fablecut-data/project.json`. Bạn có thể bấm nút **Export** ở góc trên bên phải web bất cứ lúc nào.

### Cách 2: Nhắn AI Agent sửa trực tiếp (Qua cửa sổ Chat)
*Phù hợp nhất khi muốn sửa hàng loạt (ví dụ: đổi style tất cả các câu chữ, chuẩn hóa âm thanh, dịch mốc giây chính xác đến từng phần trăm giây):*
- Chỉ cần gõ yêu cầu như các mẫu ở **Mục IV - Bước 2.C** phía trên.
- Ngay khi Agent báo đã patch xong, màn hình trình duyệt `localhost:7777` của bạn cũng tự động nhảy theo kết quả mới.

### Cách 3: Sửa file kịch bản gốc (`.capcut.json`) rồi chạy lại Adapter
*Phù hợp nhất khi bạn muốn viết lại kịch bản từ gốc, chia lại phân đoạn (`segments`) hoặc áp dụng sang một `template` hoàn toàn khác:*
1. Mở file `D:\HOANG HA\Deverlopper Software\FableCut-Studio\fablecut-data\media\<video_id>\<video_id>_commentary.capcut.json` bằng trình soạn thảo (VS Code / Cursor).
2. Sửa các trường `time_range`, `text_overlay`, `sfx_cue` hoặc `style`.
3. Nhắn Agent: *"Chạy lại `adapter/convert.py` cho file JSON của video `<video_id>` và cập nhật lại lên timeline"* (hoặc tự chạy lệnh Python ở Mục VI bên dưới).

---

## VI. QUY TRÌNH TỰ ĐỘNG BẰNG PYTHON (DÒNG LỆNH CLI)

Nếu bạn muốn tích hợp vào code Python của bạn hoặc chạy bằng dòng lệnh:

### 1. Bước chuyển đổi (Validate & Tự đăng ký Media & Sinh lệnh Patch)
Chạy script `adapter/convert.py` trỏ thẳng vào file JSON trong thư mục của video:
```powershell
py -3.10 adapter/convert.py --json "..\fablecut-data\media\<video_id>\<video_id>_commentary.capcut.json" --output "adapter/ops.json"
```

- **Tự động nhận diện & đăng ký media**: Script tự tìm video/audio trong `fablecut-data/media/<video_id>/` (hoặc thư mục cha của file JSON nếu nằm trong `media/`), đo thông số kỹ thuật bằng `ffprobe` và tự chèn op `addMedia` / `relinkMedia` vào đầu danh sách lệnh patch.
- **Tùy chọn bổ sung**:
  - `--video-id <id>` / `--audio-id <id>`: Chỉ định thủ công `mediaId` có sẵn trong `project.json`.
  - `--data-dir "<path>"`: Chỉ định thư mục `fablecut-data` (mặc định đọc `FABLECUT_DATA_DIR` hoặc `D:\HOANG HA\Deverlopper Software\FableCut-Studio\fablecut-data`).
  - `--no-auto-media`: Tắt tự động sinh op `addMedia`/`relinkMedia`, chỉ dùng media đã đăng ký sẵn.
  - `--template <id>` / `--duration <giây>`: Ghi đè template hoặc tổng thời lượng.
- Nếu file JSON **sai cấu trúc**, script sẽ báo lỗi ngay lập tức và dừng lại (bảo vệ timeline). Nếu hợp lệ, `ops.json` sẽ được xuất ra sẵn sàng cho `fablecut_patch_project`.

---

## VII. TÙY BIẾN GIAO DIỆN CHỮ & PRESETS (`presets/styles.json` & `presets/templates/`)

Toàn bộ phong cách chữ (Title Styles) được lưu tại `presets/styles.json` và 6 mẫu cấu trúc nhịp điệu nằm tại `presets/templates/`. AI chỉ được chọn từ danh sách này, không tự bịa phong cách lạ:

### 1. Các Style chữ có sẵn (`presets/styles.json`):
1. **`HIGHLIGHT_YELLOW`** / **`highlight-yellow`**: Font *Bebas Neue*, chữ hoa, màu trắng viền đen, highlight vàng hổ phách (`#ffd166`), hiệu ứng nảy từng từ (`word-pop`).
2. **`IMPACT_RED`** / **`BOLD_RED`**: Font *Anton*, chữ hoa dày dặn, dải màu trắng - đỏ (`#ff4444`), viền đen dày, hiệu ứng `highlight` + `shake`.
3. **`CLEAN_WHITE`** / **`clean-white`**: Font *Inter*, chữ trắng tinh gọn, nền mờ dễ đọc, hiệu ứng `rise-mask` / `word-slide`.
4. **`NEON_GLOW`** / **`neon-glow`**: Font *Inter* đậm, highlight xanh neon (`#39ff14`) phát sáng (`glow`), hiệu ứng `karaoke`.
5. **`BOLD_CONTRAST`** / **`bold-contrast`**: Font *Inter* đậm, highlight xanh cyan (`#22d3ee`), hiệu ứng `word-pop`.
6. **`HANDWRITTEN_WARM`** / **`handwritten-warm`**: Font *Playfair Display*, tông kem vàng ấm áp, hiệu ứng `rise-mask`.
7. **`CLEAN_CYAN`**: Font *Montserrat*, màu xanh neon (`#22d3ee`), hiệu ứng quét chữ mượt (`clip-reveal`).
8. **`ELEGANT_GOLD`**: Font *Playfair Display*, phong cách sang trọng, dải màu trắng sang vàng kim, hiệu ứng `clip-reveal`.

### 2. Các Template nhịp điệu (`presets/templates/`):
- `shock-hook`: Mở đầu gây sốc mạnh, nhịp nhanh.
- `how-it-works`: Giải thích quy trình / cơ chế từng bước (kèm icon SVG `step-1..3`).
- `satisfying`: Nhịp mượt, tập trung vào hình ảnh & âm thanh thỏa mãn.
- `story`: Kể chuyện theo mạch dẫn dắt.
- `before-after`: So sánh trước - sau.
- `hazard-rescue`: Cảnh báo nguy hiểm / tình huống giải cứu kịch tính.

### 3. Cách thêm Style mới:
Mở file `presets/styles.json` và thêm một khối style mới:
```json
{
  "TIKTOK_VIRAL": {
    "font": "Archivo Black",
    "fontSize": 84,
    "color": "#ffff00",
    "strokeWidth": 8,
    "strokeColor": "#000000",
    "textAnim": "word-pop",
    "wordRate": 0.16,
    "uppercase": true,
    "y": 300,
    "presetAnimation": "pop-in"
  }
}
```
Sau đó trong file kịch bản JSON (hoặc khi nhắn cho Agent), chỉ cần ghi `"style": "TIKTOK_VIRAL"`.

---

## VIII. NƠI LƯU TRỮ KẾT QUẢ

- Tất cả video render ra đều nằm tại thư mục:  
  `D:\HOANG HA\Deverlopper Software\FableCut-Studio\fablecut-data\exports\`
- File vừa render thử nghiệm thành công:  
  `D:\HOANG HA\Deverlopper Software\FableCut-Studio\fablecut-data\exports\Agricultural irrigation and spraying in an orchard hillside_shorts_1080x1920.mp4`
  *(Chuẩn 1080x1920, 30fps, 31.43 giây, chuẩn YouTube Shorts & TikTok)*.

---

## IX. DỌN DẸP THEO LÔ SAU 10–20 VIDEO (`cleanup.py`)

Sau khi hoàn tất 10–20 video và đã kiểm tra thành phẩm trong `fablecut-data/exports/`, bạn có thể giải phóng dung lượng nhanh chóng bằng script `cleanup.py` trong `fablecut-bundle`:

### Nguyên tắc bảo vệ an toàn của `cleanup.py`
- **Các thư mục được dọn**:
  - `youtube-analyst-niches-forest/temp/` (file tải về/trung gian còn sót, giữ lại `.gitkeep`).
  - `fablecut-data/media/<video_id>/` (thư mục nguồn của từng video đã làm xong) và các file media rời ở gốc `media/`.
  - `fablecut-data/analysis/proxies/` và `analysis/frames/` (cache xem trước tự sinh, dùng `--skip-cache` nếu muốn giữ lại).
- **Tuyệt đối KHÔNG BAO GIỜ XÓA**:
  - `fablecut-data/exports/` (toàn bộ video Shorts 9:16 đã render).
  - `fablecut-data/library/` (SFX, fonts, SVG, elements).
  - `fablecut-data/projects/` (kho lưu các project của FableCut — nếu muốn dọn project cũ, hãy dùng chức năng **Archive → Delete** ngay trên giao diện FableCut hoặc `fablecut_projects`).
  - Các thư mục/file trong `media/` đang được tham chiếu bởi `fablecut-data/project.json` hiện mở (trừ khi bạn cố tình truyền `--include-active`).

### Cách 1: Nhấp đúp `cleanup.bat` (Menu trực quan)
Nhấp đúp vào `cleanup.bat` trong `fablecut-bundle\` để mở menu chọn nhanh:
- `[1]` Xem trước danh sách dọn dẹp (`--dry-run`, an toàn tuyệt đối)
- `[2]` Dọn lô cũ, giữ lại `N` video mới nhất (tự xem trước rồi mới hỏi xác nhận `[y/N]`)
- `[3]` Dọn các mục cũ hơn `N` ngày
- `[4]` Dọn riêng theo mã `video_id`
- `[5]` Dọn toàn bộ media/temp không còn trong project đang mở

Hoặc chạy nhanh từ dòng lệnh:
```powershell
.\cleanup.bat preview      # Xem trước toàn bộ file có thể dọn
.\cleanup.bat keep 3       # Giữ lại 3 video mới nhất (hỏi xác nhận trước khi xóa)
.\cleanup.bat days 7       # Dọn các mục cũ hơn 7 ngày (hỏi xác nhận trước khi xóa)
```

### Cách 2: Chạy trực tiếp bằng Python (`cleanup.py`)
Luôn chạy `--dry-run` trước để xem trước danh sách file sẽ bị xóa và dung lượng giải phóng:

```powershell
# 1. Xem trước toàn bộ những gì có thể dọn (AN TOÀN - chưa xóa gì)
py -3.10 cleanup.py --dry-run

# 2. Giữ lại 3 thư mục video mới nhất trong media/, chỉ dọn các video cũ hơn
py -3.10 cleanup.py --keep-latest 3 --dry-run

# 3. Chỉ dọn các video/temp cũ hơn 7 ngày
py -3.10 cleanup.py --older-than-days 7 --dry-run

# 4. Dọn riêng một hoặc nhiều video_id cụ thể
py -3.10 cleanup.py --video-id snaptik.vn_7611044561959324946 --dry-run

# 5. Thực thi xóa thật sau khi đã kiểm tra kỹ output dry-run
py -3.10 cleanup.py --keep-latest 3 --yes
```

---

## X. XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

1. **Lỗi "9Router chưa chạy ở cổng 20128"**:
   - Kiểm tra ứng dụng 9Router đã được khởi động chưa.
   - Mở terminal gõ: `curl.exe http://localhost:20128/v1/models` để kiểm tra.
2. **Lỗi không kết nối được FableCut cổng 7777**:
   - Chạy `node "D:\HOANG HA\Deverlopper Software\FableCut-Studio\FableCut\server.js"` để bật lại server.
3. **Lỗi Schema Validation Error khi chạy `convert.py`**:
   - Kiểm tra file JSON của bạn xem có thiếu trường bắt buộc nào không (`segments`, `time_range`, `start`, `end`, `text_overlay`, `text`, `style`).
   - Sửa lại file JSON theo đúng cấu trúc mẫu trong `examples/` rồi chạy lại.
