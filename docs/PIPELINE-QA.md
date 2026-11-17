# Pipeline validation and QA

> Run the commands below from the `fablecut-bundle/` directory (the one containing `adapter/`, `scripts/` and `examples/`).

`examples/` is the read-only fixture set. Validation and compilation must not modify fixture files. Keep generated patch operation JSON in a temporary/output directory, not in `examples/`.

## Validate every input fixture

```powershell
py -3.10 scripts/qa_check.py --all-examples
```

Legacy fixtures may retain gaps or end slightly beyond declared duration; they are schema-validated and checked for invalid ranges/overlap without applying strict continuity rules.

QA also checks that every template/style font resolves to a `.woff2` stem in `fablecut-data/library/fonts/`. Compiler ops checks first-frame text visibility, one `transitionIn` on the first V1 cut per beat, bounded video cuts, non-empty/non-overlapping A2 cues, before/after labels with distinct source offsets, and V3 SVG separation from top-positioned V2 captions.

The backend pytest suite validates exported interchange JSON against `fablecut-bundle/schema/input_schema.json` before writing/syncing it, checks canonical catalog SFX routes, and covers the contiguous TTS timing path. The default export root is `youtube-analyst-niches-forest/exports/`; only explicit `EXPORTS_DIR` (or legacy `FABLECUT_MEDIA_DIR`) overrides it.

## Compile and check one fixture

```powershell
py -3.10 adapter/convert.py --json examples/irrigation-how-it-works.json --output "$env:TEMP\how-it-works.ops.json"
py -3.10 scripts/qa_check.py --input examples/irrigation-how-it-works.json --ops "$env:TEMP\how-it-works.ops.json"
```

Apply generated operations only after reviewing them and explicitly approving a test project. The compiler only removes clips whose IDs begin with `fcpipe_`; it leaves unrelated project clips and locked clips untouched. It never writes `project.json` itself.

## Render QA

```powershell
py -3.10 scripts/qa_check.py --render path\to\short.mp4 --duration 31.44
```

The render check requires `ffprobe` and `ffmpeg`. It verifies 1080x1920, `yuv420p`, AAC 48 kHz when audio is present, duration tolerance, and loudness/peak when ffmpeg emits those measurements.

Do not treat successful schema/ops validation as proof of visual correctness. Frame 0, beat boundaries, overlays, safe-box and final audio still require inspection of actual rendered output before marking a template verified.
