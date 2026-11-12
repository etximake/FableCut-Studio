# AGENTS.md

Monorepo for building 9:16 vertical short videos across four separated layers: analysis (`youtube-analyst-niches-forest/`), upstream editor engine (`FableCut/`), deterministic pipeline adapter/QA (`fablecut-bundle/`), and externalized runtime data (`fablecut-data/`).

## Directory boundaries & invariants

- **`FableCut/`** — Upstream FableCut v1.18.0 Node editor (`server.js`, `mcp-server.js`, `app.js`, zero npm dependencies). **Do not modify core `FableCut/` files** for studio pipeline work. If explicitly editing FableCut itself, follow `FableCut/AGENTS.md` and `FableCut/CLAUDE.md`.
- **`fablecut-bundle/`** — Pipeline schema (`schema/input_schema.json`), presets (`presets/styles.json`, `presets/templates/`), compiler (`adapter/convert.py`), QA (`scripts/qa_check.py`), server/cleanup scripts, and MCP configs (`opencode.json`, `antigravity.json`).
- **`youtube-analyst-niches-forest/`** — Python FastAPI service (`main.py`) with its own `.venv/` and `.env` that extracts 3x3 contact sheets, generates commentary JSON/SRT/voiceover, and exports per-`video_id` bundles to `fablecut-data/media/<video_id>/`.
- **`fablecut-data/`** — External `FABLECUT_DATA_DIR` (`project.json`, `projects/`, `media/<video_id>/`, `exports/`, `analysis/`, `library/`). Runtime media/exports/projects are gitignored; do not overwrite or re-render existing project/export assets unless requested.
- **`docs/`** — Consolidated docs (`docs/PIPELINE-QA.md`, `docs/HUONG-DAN-SU-DUNG.md`, `docs/PROJECT_MODELS.md`). Treat `docs/archive/` and `docs/design/` as historical only.

## Commands

Run commands inside each subproject directory (Windows / PowerShell).

### FableCut server (`fablecut-bundle/`)

Always start via `server.bat` so `FABLECUT_DATA_DIR` points to `fablecut-data/` (running bare `node server.js` inside `FableCut/` uses `FableCut/` as its data dir instead):

```powershell
.\server.bat start      # Start FableCut on http://localhost:7777
.\server.bat status     # Check PID on port 7777
.\server.bat stop       # Stop server on port 7777
.\server.bat restart
```

### Pipeline QA & adapter (`fablecut-bundle/`)

Use `py -3.10` (`tests/test_pipeline_qa.py` invokes `py -3.10` explicitly, and `convert.py` / `qa_check.py` require `jsonschema` with no fallback):

```powershell
py -3.10 -m pytest -q                                           # All pipeline tests
py -3.10 -m pytest tests/test_pipeline_qa.py -k <test_name>     # Single test
py -3.10 scripts/qa_check.py --all-examples                     # Validate fixtures + .woff2 fonts in fablecut-data/library/fonts/
py -3.10 adapter/convert.py --json examples/<file>.json --output "$env:TEMP\out.ops.json"
py -3.10 scripts/qa_check.py --input examples/<file>.json --ops "$env:TEMP\out.ops.json"
py -3.10 scripts/qa_check.py --render <path.mp4> --duration <seconds>   # Requires ffmpeg + ffprobe
```

### Video analyst service (`youtube-analyst-niches-forest/`)

Use the subproject venv:

```powershell
.\.venv\Scripts\python.exe -m pytest -q                         # All backend tests (24 tests)
.\.venv\Scripts\python.exe -m pytest tests/<file>.py -k <name>  # Single test
.\run.bat                                                       # Start FastAPI server (main.py)
```

### FableCut engine tests (`FableCut/`)

No `npm install` needed (uses `node:test` and Node >= 18):

```powershell
npm test                                  # Full FableCut suite
node --test test/<file>.test.js           # Single test file
```

### Safe batch cleanup (`fablecut-bundle/`)

```powershell
.\cleanup.bat preview                     # Dry-run: shows temp/ and media/ cleanup targets
```

`cleanup.py` protects `fablecut-data/exports/`, `library/`, `projects/`, and media referenced by `fablecut-data/project.json`.

## Pipeline & environment quirks

- **Timeline edits via MCP**: Use `fablecut_patch_project` rather than overwriting `project.json` on partial edits. `fablecut-bundle/opencode.json` and `antigravity.json` configure the `fablecut` stdio MCP server with `FABLECUT_DATA_DIR` set to `fablecut-data/`.
- **Compiler scope**: `adapter/convert.py` only emits ops; it never writes `project.json`, and generated cleanup only removes clips with IDs prefixed `fcpipe_` (leaving user/locked clips untouched). Use only defined presets/templates in `fablecut-bundle/presets/` rather than inventing effect or style names.
- **Read-only fixtures**: Never write generated `.ops.json` or test outputs into `fablecut-bundle/examples/`; write to `$env:TEMP`.
- **QA vs visual truth**: Passing `qa_check.py --input --ops` does not verify Frame 0 rendering, safe-box margins, overlays, or final audio mix; inspect rendered frames/output (`fablecut_frame`) before marking a template verified.
- **Analyst config reload**: `youtube-analyst-niches-forest/src/core/config.py` (`DynamicSettings`) re-reads `.env` via `dotenv_values` on lookup, overriding `os.environ` when a key exists in `.env`. `tests/conftest.py` isolates `EXPORTS_DIR` and `TEMP_DIR` during pytest.
- **FableCut Windows test flags**: Custom Node tests spawning `server.js` or `mcp-server.js` against temp data dirs should set `FABLECUT_NO_FS_WATCH=1` (prevents Windows libuv abort on watched temp dirs) and `FABLECUT_NO_AUTOSTART=1` (prevents detached `server.js` orphans).
- **Secrets & 9Router**: Never write real API keys into files; `9Router` (`http://localhost:20128/v1`) reads `{env:ROUTER_API_KEY}` and requires direct provider API keys (no subscription OAuth). Do not alter `9Router` security/bind configuration unless asked.

## Existing instruction sources

- `fablecut-bundle/AGENTS.md` — 9Router + OpenCode + FableCut setup and operational rules (Vietnamese).
- `FableCut/AGENTS.md` & `FableCut/CLAUDE.md` — Full FableCut schema, MCP tool contracts, props, and compositor behavior.
- `docs/PIPELINE-QA.md` — Validation and render QA checklist.
