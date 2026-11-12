# 6 Video Templates — README for the coding agent

Read this file + `templates/index.json` first. Do not invent templates.

## Files

```
video-templates-5/
  README-AGENT.md            <- this file
  templates/index.json       <- registry + decision tree, read first
  templates/shock-hook.json
  templates/how-it-works.json
  templates/satisfying.json
  templates/before-after.json
  templates/story.json
  examples/irrigation-<template>.json   <- same 31.44s irrigation clip, styled 6 ways
```

Copy `templates/` into the project as `presets/templates/`. Keep template files OUTSIDE the FableCut repo.

## The 6 templates (one line each)

| template_id | Use when |
|---|---|
| `hazard-rescue` | Hoof abscess, limping animal, machine breakdown, emergency fix |
| `shock-hook` | Surprising fact / number / price in the first 3s |
| `how-it-works` | Explains how a machine/process works in steps |
| `satisfying` | The work itself is satisfying to watch, minimal text |
| `before-after` | Clear transformation, old vs new |
| `story` | About a person / a job, problem -> turn -> payoff |

Full definitions (structure, text, animation, transition, filter, motion, SFX) are in each `templates/<id>.json`. Each template changes beat order and length, not just colours.

## How the agent applies a template

1. Stage 1-2 produce the content layer: segments, time_range, voiceover, text_overlay, sfx_cue.
2. Agent picks ONE `template_id` using `templates/index.json` decision tree.
3. Agent merges the template's style layer (`per_beat_style`, `text_defaults`, `captions`, `layout`, `sfx_defaults`) into the video JSON. Content (voiceover, timings) is NOT rewritten to fit the template.
4. Agent validates JSON, then applies with `fablecut_patch_project` (patch, not full rewrite).
5. Agent renders and checks timings. Report: template_id, version, any per-video override.

## Changing a template (3 levels — do not confuse them)

1. **Per-video override** — change style fields in that video's JSON only. Template file unchanged.
   - Command example: "Change this video to template satisfying, keep voiceover and timings, only change the style layer."
2. **Permanent template change** — edit `templates/<id>.json`, bump `version` (1.0.0 -> 1.1.0), old videos unchanged, test-render 1 clip first.
   - Command example: "Update template how-it-works: font_size 64 -> 72, save to presets/templates/how-it-works.json. Old videos do not change, future videos use the new version."
3. **New variant** — copy a template file to a new `template_id` (e.g. `shock-hook-v2`), change only the listed fields, add it to `templates/index.json`.
   - Command example: "Create template shock-hook-v2 from shock-hook, only change transition whip-pan to glitch, keep everything else."

## Hard rules

- ONLY use `template_id`, `text_anim`, `transitions`, `filters` listed in the chosen template file (`allowed_effects_only`). Never invent a new name.
- One video = one template. Do not mix two templates in one video.
- Text: max 4 words per beat for shock-hook / satisfying / before-after, max 6 for how-it-works / story. Keep text inside 9:16 safe area.
- `time_range` must be contiguous: next start == previous end, total 30-60s.
- Validate JSON before every patch. Invalid JSON: stop and report, do not patch.
- Do NOT edit FableCut core (`server.js`, `mcp-server.js`). Templates live in the project, not in the FableCut repo.
- FableCut export still needs an open browser — pipeline is semi-automated, not fully headless.

## Test the 5 templates (first run)

Apply all 5 `examples/irrigation-<template>.json` to the same irrigation clip, render 5 x 31s Shorts, compare. Keep the 3 that look most distinct, note the other 2 in the log. Do not ship all 5 to the channel before this comparison.
# DEPRECATED

The canonical template registry is now `presets/templates/` (registry `1.1.0`). This directory is retained only for historical compatibility; do not add templates or resolve new template IDs from here.
