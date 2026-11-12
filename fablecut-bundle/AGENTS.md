# AGENTS.md - Cai dat va van hanh FableCut qua 9Router

## Muc tieu
Thiet lap pipeline: 9Router (cong LLM) -> OpenCode (agent) -> FableCut (editor, qua MCP).
Sau khi cai xong, agent phai render thu duoc 1 video Short doc 9:16 tu file JSON mau.

## Nguyen tac bat buoc
1. KHONG sua code loi cua FableCut: server.js, mcp-server.js, app.js giu nguyen nhu repo goc.
2. Moi cau hinh nam trong opencode.json cua du an nay.
3. Moi code rieng (adapter, preset, schema) nam trong thu muc cua du an nay, KHONG nam trong thu muc FableCut.
4. API key chi doc tu bien moi truong ROUTER_API_KEY. Khong ghi key that vao bat ky file nao.
5. Chi dung API key truc tiep cua nha cung cap qua 9Router. KHONG dung dang nhap OAuth cua goi dang ky (Claude Pro/Max, Codex) qua 9Router.
6. Dung fablecut_patch_project de sua timeline. Khong ghi de toan bo project.json neu chi sua mot phan.

## Buoc 1 - Kiem tra may
Chay va bao cao ket qua:
- node --version ; git --version ; ffmpeg -version
- curl http://localhost:20128/v1/models
Neu 9Router khong tra ve danh sach mo hinh: DUNG LAI, bao cao "9Router chua chay o cong 20128", khong lam tiep.
Kiem tra 9Router da o phien ban 0.4.44 tro len, da dat JWT_SECRET rieng, va chi bind 127.0.0.1.
Neu chua, canh bao ro rang trong bao cao, khong tu y doi cau hinh bao mat.

## Buoc 2 - Clone FableCut (khong sua code)
CHI dung dung link nay:
git clone https://github.com/ronak-create/FableCut
Kiem tra: owner ronak-create, repo FableCut, co file mcp-server.js va server.js.
Dat bien FABLECUT_DATA_DIR tro ra NGOAI thu muc repo, de project.json, media/, exports/ nam rieng va khong bi mat khi cap nhat FableCut.

## Buoc 3 - Tao opencode.json cho du an
Tao file opencode.json gom 2 phan:
a) Plugin 9Router: "@vheins/opencode-9router@latest" trong khoa "plugin" (OpenCode V1) hoac "plugins" (V2). Plugin tu phat hien mo hinh tai localhost:20128.
b) MCP server FableCut, dang stdio:
   "mcp": { "fablecut": { "type": "local", "command": ["node", "<duong-dan-tuyet-doi>/FableCut/mcp-server.js"] } }
Dung duong dan tuyet doi that tren may nay, khong de placeholder. Key trong file chi ghi "{env:ROUTER_API_KEY}".

## Buoc 4 - Khoi dong va kiem chung ket noi
- Chay: node server.js trong thu muc FableCut.
- Xac nhan editor mo duoc tai http://localhost:7777
- Trong OpenCode: go /models, chon 1 mo hinh qua 9Router.
- Goi fablecut_status. Neu loi: bao cao nguyen van loi, kiem tra lai duong dan mcp-server.js va cong 7777.

## Buoc 5 - Ghim mo hinh theo chang
- Chang 1 (doc anh luoi 3x3): ghim 1 mo hinh vision co tool calling, da test rieng truoc. Ghi ten mo hinh vao file PROJECT_MODELS.md cua du an.
- Chang 2 (viet loi binh + chon preset): ghim 1 mo hinh text re hon.
- Tat fallback sang nhom mo hinh yeu hon cho chang 1.

## Buoc 6 - Tao adapter va thu vien preset
- adapter/convert.py: doc JSON khung (segments, time_range, voiceover, text_overlay, sfx_cue) + lop style, sinh lenh fablecut_patch_project.
- presets/: chi dung preset da dinh nghia san. AI chi duoc CHON preset, khong tu bia ten hieu ung moi.
- Validate JSON theo schema TRUOC moi lan patch. JSON sai schema thi dung lai va bao cao, khong patch thu.

## Buoc 7 - Render thu va bao cao
Dung file JSON mau clip tuoi cay 31 giay trong examples/ (4 doan: 0-4.5s, 4.5-17.5s, 17.5-26s, 26-31.44s).
Patch tung doan, render ban 9:16, doi chieu moc giay.
Bao cao cuoi: tung buoc dat / chua dat, loi nguyen van neu co, ten mo hinh da ghim, duong dan file xuat.
