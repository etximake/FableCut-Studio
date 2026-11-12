# Viewer-perspective limitations — irrigation Shorts (project rev 41)

This note records observable limitations in the existing rendered Short and the timeline that produced it. It is diagnostic evidence, not authorization to edit or re-render `fablecut-data/project.json` or its MP4. Both remain read-only.

## What a viewer sees

- **No opening caption at frame 0.** `frame_0.jpg` shows the orchard machinery without visible title text. At `frame_1_5.jpg`, “IRRIGATING STEEP HILLS” appears in uppercase white sans-serif text inside a dark rounded pill. This is a delayed reveal, not a frame-zero hook.
- **A noticeable caption gap during action.** `frame_24.jpg` shows the water spray and pulley, but no caption. The timeline has gaps between text clips at approximately `4.16–4.5s`, `16.15–17.5s`, and `22.9–26s`; the last gap overlaps the visible water-spraying action.
- **The text treatment can distract or feel unstable.** The text clips use `word-pop`, opacity animation from 0 to 1, scale keys including `0 → 1.12 → 1 → 1.52`, zero `boxW`/`boxH`, `boxFit: false`, and `bgOpacity: 0`. These settings explain why the text is not a consistently framed, persistent caption treatment. The compositor in `FableCut/app.js` (`15378–15849`) explicitly skips `word-pop` at clip-local time 0, so it cannot supply visible text on the first frame.
- **The base footage is a single unsplit shot.** `c_video_v1` occupies V1 for `31.438s` with `volume: 0`; it has no retention-cut segmentation in this project. Empty V3 and A2–A4 tracks mean there are no corresponding overlay/SFX clips on those tracks.
- **Voiceover level and duration are mismatched in the project.** `c_audio_a1` references a `33.04s` source but is clipped to `31.438s`, and has `volume: 1.56`. This is a project-level gain above unity, not a measured loudness guarantee.

The accompanying `rendered_shorts_3x3.jpg` contact sheet is useful for broad composition, but individual-frame inspection is needed to identify the frame-zero and caption-gap issues above. The measured render audio was **−12.8 LUFS integrated** and **−1.2 dBFS peak**: louder than the pipeline's −14 LUFS target, while the observed peak is below the −1.0 dBFS ceiling. These are measurements of this existing render, not a claim that every export has the same levels.

## Verified implementation contracts

- `FableCut/app.js` (`15604–15776`) renders several text animations (`none`, `highlight`, `karaoke`, `wave`, `bounce`, `shake`, `font-cut`) at local time zero; reveal-style animations including `word-pop` return/skip there.
- `FableCut/delivery.js` (`176–237`) defines export presets and audio delivery behavior; it does not retroactively normalize the existing project timeline.
- `FableCut/templates.js` (`57–115`) defines named entrance presets and their keyframes. A preset name is a concrete animation contract, not a guarantee that a separate clip's own text animation is visible at frame zero.

## Scope and evidence

Observed source: `fablecut-data/project.json` (revision 41); rendered evidence: `frame_0.jpg`, `frame_1_5.jpg`, `frame_24.jpg`, and `rendered_shorts_3x3.jpg` from the inspection set; audio analysis: −12.8 LUFS / −1.2 dBFS. No source project, render, or `FableCut/` file was changed to prepare this note.
