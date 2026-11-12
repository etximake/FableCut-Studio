# Kế hoạch đồng bộ dữ liệu và template giữa bốn dự án

**Phạm vi:**

- `youtube-analyst-niches-forest` — phân tích video, tạo kịch bản, TTS và xuất tài nguyên.
- `fablecut-bundle` — hợp đồng dữ liệu, registry/template, preset, adapter và QA.
- `FableCut` — editor và giao diện MCP/API để thao tác project/timeline.
- `fablecut-data` — project, media, library và kết quả render.

**Mục tiêu:** thống nhất luồng dữ liệu từ đầu vào đến timeline/render; đảm bảo chọn template có thể tái lập; phát hiện lỗi trước khi patch; không sửa mã nguồn gốc của FableCut.

**Nguyên tắc:** tài liệu này là kế hoạch, không tự cấp quyền chỉnh sửa bốn dự án. Thực hiện theo từng giai đoạn, xác nhận đầu ra và kiểm tra regression trước khi chuyển giai đoạn. Giữ nguyên cảnh báo bảo mật hiện có cho đến khi chủ hệ thống xác nhận thay đổi.

## 1. Đích kiến trúc

```text
youtube-analyst-niches-forest
  video / URL → phân tích hình ảnh → visual timeline → commentary JSON
  TTS + media assets → fablecut-data/media/<asset-folder>/
                         │
                         ▼
fablecut-bundle
  canonical schema → template registry + template spec
  validator → deterministic adapter/compiler → FableCut patch operations
                         │
                         ▼
FableCut MCP ──patch ops──> fablecut-data/project.json
                         │
                         ▼
                  frame checks → export → QA
```

Phải đặt tên và version riêng cho ba lớp dữ liệu, không dùng chung tên “CapCut JSON”:

1. **Commentary/story interchange:** dữ liệu nội dung trung gian, độc lập editor.
2. **FableCut patch operations:** lệnh có cấu trúc gửi qua `fablecut_patch_project`.
3. **FableCut project/export:** project đang mở và file media đã render.

CapCut interchange chỉ là định dạng xuất riêng nếu pipeline thực sự cần tương thích CapCut; không dùng nó thay cho patch protocol của FableCut.

## 2. Các quyết định cần chốt trước khi triển khai

1. Chọn `presets/templates/` làm nguồn chuẩn duy nhất sau khi đối chiếu và di trú các khác biệt cần giữ từ `presets/video-templates-5/`.
2. Chốt một schema trung gian có `schema_version`, quy tắc canonical cho `template_id`/`template_version`, metadata, beat, time range, text, SFX nullable và style override.
3. Chốt một nơi lưu template ID/version. Khuyến nghị root interchange là nguồn chuẩn; nếu giữ bản sao trong `video_metadata`, validator buộc hai giá trị bằng nhau.
4. Chốt quy ước timecode: giây dạng số, `start` bao gồm, `end` không bao gồm; timeline mới liền mạch, trường hợp legacy có thể cảnh báo thay vì thất bại.
5. Chốt định danh asset: video ID nghiệp vụ tách khỏi tên file/thư mục; metadata chỉ rõ asset hoặc media key. Không chọn file media theo thứ tự alphabet khi có hơn một ứng viên.
6. Chốt trách nhiệm cấu trúc: backend tạo nội dung và chọn template; template cung cấp đặc tả dựng; adapter biên dịch; FableCut chỉ thực thi patch ops.

## 3. Các giai đoạn

### Giai đoạn 0 — Baseline và kiểm kê

- Ghi nhận phiên bản/commit và trạng thái hiện tại của từng thư mục; không ghi đè thay đổi đang có.
- Lập bảng file chuẩn và file legacy cho schema, template, styles, examples, model và media.
- So sánh hai cây template theo ID, version, cấu trúc beat, thời lượng, effect allowlist, Frame 0, safe area và layout.
- Thu thập fixtures đang chạy được: commentary JSON, media folder, project hiện tại, patch ops và render mẫu.
- Ghi lại trạng thái test/render hiện có, không suy ra “đã kiểm thử template” chỉ từ một lần render project.

**Điều kiện hoàn tất:** có báo cáo baseline và danh sách mâu thuẫn; chưa sửa code.

### Giai đoạn 1 — Hợp đồng dữ liệu chuẩn

- Viết đặc tả interchange trung lập với editor và JSON Schema tương ứng.
- Đồng bộ `src/models/schemas.py`, prompt/engine, fixtures và `fablecut-bundle/schema/input_schema.json` với cùng trường, enum và nullable behavior.
- Chuẩn hóa beat cho sáu template: `hazard-rescue`, `shock-hook`, `how-it-works`, `satisfying`, `before-after`, `story`; cho phép legacy có kiểm soát.
- Định nghĩa kiểm tra time range: giá trị hữu hạn, `0 <= start < end <= duration`, thứ tự không giảm; chế độ strict cho nội dung mới và warning/migration cho legacy.
- Chốt quy tắc `template_id`/version, ngôn ngữ, SFX nullable, voiceover translation, visual hint và style override.
- Không để validator nhẹ kiểu “chỉ kiểm tra có schema_version và segments” thay thế JSON Schema đầy đủ.

**Điều kiện hoàn tất:** cùng một bộ test JSON cho phép/loại giống nhau ở Pydantic và JSON Schema; lỗi chỉ ra path và nguyên nhân.

### Giai đoạn 2 — Một nguồn template và phiên bản hóa

- Chỉ định `presets/templates/index.json` là registry chuẩn; mỗi template ID chỉ có một file chuẩn.
- Di trú khác biệt có chủ đích từ `presets/video-templates-5/`; đánh dấu nguồn cũ deprecated sau khi tìm hết tham chiếu.
- Đồng bộ README, chỉ số “5/6”, version registry, version từng template và ví dụ.
- Quy định version template được ghi lại trên từng interchange và log render để tái lập kết quả cũ.
- Validate template files: beat order, tỷ lệ/thời lượng, allowed effects, trường SFX, beat đầu hiển thị Frame 0 và vùng an toàn.
- Quy định khi template chỉ gợi ý cấu trúc: backend không tự đổi nội dung/voiceover để ép vào template.

**Điều kiện hoàn tất:** adapter, backend và tài liệu tra cùng một registry; không có fallback im lặng sang thư mục legacy.

### Giai đoạn 3 — Backend tạo interchange có thể tiêu thụ

- Backend nhận template ID rõ ràng khi người dùng chọn; nếu để tự động, ghi rõ lý do/nguồn chọn.
- Đưa cấu trúc beat của template vào prompt; kiểm tra beat sinh ra hợp lệ với template đã chọn.
- Sửa mapping skill/template để dùng đúng ID skill trong registry hiện hành.
- Đồng bộ Pydantic với schema chuẩn, bao gồm `template_id/version`, nullable SFX và style override được cho phép.
- Làm rõ đầu ra của rewrite: giữ nguyên template trừ khi người dùng đổi; không âm thầm chọn lại.
- Kẹp thời điểm TTS theo timeline/đoạn kế tiếp và tổng thời lượng; test audio dài hơn footage.
- Mở endpoint/contract danh sách template nếu UI cần; dropdown và API cùng dùng registry chuẩn.

**Điều kiện hoàn tất:** backend tạo fixtures hợp lệ cho cả sáu template; metadata, beat và timecode được kiểm tra tự động.

### Giai đoạn 4 — Adapter/compiler sang FableCut

- Định nghĩa rõ input là interchange đã validate; output là danh sách patch ops, không phải project JSON hoàn chỉnh.
- Viết bảng ánh xạ từng trường template → FableCut clip/track/props/operation; từ chối trường không hỗ trợ thay vì bỏ qua im lặng.
- Tách rõ `text_anim`, `preset_anim`, `transition_in`, `filter`, `motion`, SFX cue và SVG overlay; không gán nhầm text animation vào `applyPreset`.
- Kiểm tra tên/enum hiệu ứng theo template và khả năng thực thi trong FableCut trước khi sinh ops.
- Xử lý beat đầu: nội dung nhìn thấy tại Frame 0, không transition/preset vào che khuất; xác minh bằng frame thật.
- Ánh xạ position/safe-box; hỗ trợ beat layout đặc biệt như split-screen chỉ khi mapping đã được implement và test.
- Phân biệt thời lượng nội dung, thời lượng clip nguồn và duration audio; không tự cắt hay kéo giãn không được khai báo.
- Media resolution phải deterministic: explicit media ID/path → khớp metadata → fallback có kiểm tra tính duy nhất; nhiều kết quả thì dừng và báo lỗi.
- Phân tích project hiện hành trước khi patch; không xóa/thay toàn timeline mặc định. Chỉ remove/update clip do pipeline sở hữu, bỏ qua clip/track khóa và giữ asset người dùng.
- Gửi chỉnh sửa bằng `fablecut_patch_project`; không ghi đè toàn bộ `project.json` cho thay đổi cục bộ.

**Điều kiện hoàn tất:** ops JSON kiểm thử được, patch lặp lại có tính idempotent, không làm mất clip/media ngoài phạm vi pipeline.

### Giai đoạn 5 — Đồng bộ asset, project và export

- Chuẩn hóa cấu trúc media theo video/asset và quy ước URI `/media/...`; đảm bảo JSON không phụ thuộc đường dẫn tuyệt đối của máy khác.
- Đồng bộ tên `video_id`, thư mục media, file video, voiceover và metadata; thêm test cho tên có dấu, khoảng trắng, prefix download và tên trùng.
- Không chọn nhầm voiceover khi thư mục chứa nhiều file âm thanh; metadata phải định danh chính xác.
- Quy định ai tạo/copy tài nguyên và thời điểm cleanup; không xóa file đầu vào hay tài nguyên mà project đang tham chiếu.
- Ghi project ID/revision trước và sau patch; kiểm tra kết quả bằng `fablecut_get_project`.
- Khóa cấu hình export (canvas, fps, preset, loudness/true peak nếu được hỗ trợ) và xác thực file thực tế bằng ffprobe/đo âm thanh.

**Điều kiện hoàn tất:** media được resolve đúng, project phản ánh các ops và artifact export khớp đặc tả.

### Giai đoạn 6 — QA và xác nhận template

- Tạo kiểm tra tự động cho input schema, template version/beat, time range, media mapping, patch ops, Frame 0, safe-box và hiệu ứng cho phép.
- Kiểm tra track/audio: không chồng SFX ngoài chủ ý, voiceover không vượt timeline, nguồn âm thanh được giữ/tắt đúng template.
- Render tối thiểu một fixture cho từng template; với mỗi bản kiểm tra Frame 0, các điểm đổi beat, frame cuối, 9:16, thời lượng, audio và log.
- So sánh render với tiêu chí riêng của template, không chỉ xác nhận output 1080×1920.
- Chỉ đưa template vào trạng thái “verified” sau khi QA ghi lại input, template version, project revision, output path và kết quả.
- Chạy regression trên fixture legacy và kiểm tra dữ liệu project người dùng không bị thay đổi ngoài ý muốn.

**Điều kiện hoàn tất:** sáu template có bằng chứng render/QA; lỗi chặn batch được báo rõ, không patch tiếp.

### Giai đoạn 7 — Vận hành và quản trị thay đổi

- Cập nhật `PROJECT_MODELS.md` với model đã test cho từng pha, khả năng vision/tool calling và ngày xác nhận; không ghi thông tin bí mật.
- Cập nhật checklist, runbook, sơ đồ dữ liệu và release notes trong cùng một thay đổi.
- Mọi thay đổi schema/template tăng version phù hợp và có migration/fixture; không thay ngược ý nghĩa version cũ.
- Chạy theo lô nhỏ trước; lưu input, ops, project revision và output để truy vết.
- Không thay đổi cấu hình bảo mật/router trong phạm vi kế hoạch nếu chưa được chủ hệ thống chấp thuận.

## 4. Ma trận trách nhiệm

| Thành phần | Sở hữu | Không nên sở hữu |
|---|---|---|
| `youtube-analyst-niches-forest` | Phân tích, commentary, beat/time range nội dung, TTS, interchange | Chi tiết nội bộ FableCut project hoặc patch ops |
| `fablecut-bundle` | Schema dùng chung, registry/template, styles, compiler, validation, QA | Bản sao không version hóa của template hoặc chỉnh sửa FableCut core |
| `FableCut` | Project schema, timeline runtime, MCP ops, preview/render | Quy tắc nghiệp vụ của commentary/template cụ thể |
| `fablecut-data` | Project đang mở, media, library, exports | Đặc tả template/schema làm nguồn chuẩn |

## 5. Rủi ro và chốt chặn

- **Schema drift:** dùng cùng fixtures để test cả producer và consumer; không duy trì enum thủ công lệch nhau.
- **Template drift:** registry duy nhất, version được ghi trên từng kết quả, không fallback im lặng.
- **Patch gây mất dữ liệu:** patch theo phạm vi sở hữu, đọc project trước khi sửa, bảo toàn clip/track khóa.
- **Media sai:** resolution deterministic và fail khi mơ hồ.
- **Render “pass” giả:** xác nhận hình ảnh, beat và audio; độ phân giải đúng không chứng minh template đúng.
- **Legacy:** tách strict validation cho nội dung mới khỏi cảnh báo/migration cho fixtures cũ.
- **Bảo mật:** không ghi API key vào file; giữ cảnh báo bind/JWT cho đến khi được xác minh và phê duyệt.

## 6. Thứ tự khuyến nghị thực hiện

1. Baseline/kiểm kê và quyết định nguồn template.
2. Chốt interchange schema và bộ fixtures hợp lệ.
3. Đồng bộ backend sinh interchange.
4. Hoàn thiện compiler sang FableCut patch ops.
5. Đồng bộ media/project/export và chạy QA từng template.
6. Cập nhật hướng dẫn vận hành, model registry và rollout theo lô.

Không bắt đầu batch render hoặc sửa hàng loạt project trước khi giai đoạn 1–4 có test pass và patch thử nghiệm đã được kiểm tra trên project mẫu.
