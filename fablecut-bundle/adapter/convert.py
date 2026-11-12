#!/usr/bin/env python3
"""
adapter/convert.py - FableCut Timeline Patch Generator
Converts structured story JSON (segments, time_range, voiceover, text_overlay, sfx_cue)
plus template presets into atomic operations for fablecut_patch_project.
"""

import sys
import os
import json
import uuid
import argparse
import subprocess
import math
import re
import hashlib
from pathlib import Path
from urllib.parse import quote, unquote

try:
    import jsonschema
except ImportError:
    jsonschema = None

VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi")
AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg", ".m4a", ".aac", ".flac")
DEFAULT_DATA_DIR = Path(
    os.environ.get("FABLECUT_DATA_DIR")
    or (Path(__file__).resolve().parents[2] / "fablecut-data")
)


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_input_json(data, schema_path):
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found at: {schema_path}")
    
    schema = load_json(schema_path)
    if jsonschema:
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.exceptions.ValidationError as e:
            raise ValueError(f"Schema validation failed: {e.message} at path: {'/'.join(str(p) for p in e.path)}")
    else:
        raise RuntimeError("Full JSON Schema validation requires the 'jsonschema' package; refusing the legacy shallow check.")

    metadata = data.get("video_metadata", {})
    duration = metadata.get("duration_seconds")
    ranges = [segment.get("time_range", {}) for segment in data.get("segments", [])]
    strict = bool(data.get("template_id") or metadata.get("template_id"))
    previous_end = None
    for index, time_range in enumerate(ranges):
        start, end = time_range.get("start"), time_range.get("end")
        if start is None or end is None or not (0 <= start < end) or (strict and end > duration):
            raise ValueError(f"Invalid time_range at segments/{index}/time_range: require 0 <= start < end <= duration_seconds ({duration}).")
        if strict and previous_end is not None and abs(start - previous_end) > 0.01:
            raise ValueError(f"Non-contiguous timeline at segments/{index}/time_range/start: expected {previous_end}, got {start}.")
        if previous_end is not None and start < previous_end - 0.01:
            raise ValueError(f"Overlapping timeline at segments/{index}/time_range/start.")
        previous_end = end


def load_template(template_id_or_path, base_dir):
    """Load template definition from file path or template_id"""
    if not template_id_or_path:
        return None
    p = Path(template_id_or_path)
    if p.exists():
        return load_json(p)
    t_path = base_dir / "presets" / "templates" / f"{template_id_or_path}.json"
    if t_path.exists():
        return load_json(t_path)
    return None


def _resolve_data_dir(data_dir=None):
    if data_dir:
        return Path(data_dir)
    env_dir = os.environ.get("FABLECUT_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return DEFAULT_DATA_DIR


def _to_media_src(file_path, media_dir):
    """Convert an absolute file inside fablecut-data/media/ into a /media/... URL src."""
    try:
        rel = Path(file_path).resolve().relative_to(Path(media_dir).resolve())
    except ValueError:
        return None
    encoded = "/".join(quote(part, safe="") for part in rel.parts)
    return f"/media/{encoded}"


def _src_to_file(src, media_dir):
    if not src or not str(src).startswith("/media/"):
        return None
    rel = unquote(str(src).split("?")[0][len("/media/"):])
    candidate = (Path(media_dir) / rel).resolve()
    media_root = Path(media_dir).resolve()
    try:
        if not candidate.is_relative_to(media_root):
            return None
    except AttributeError:
        if media_root not in candidate.parents:
            return None
    return candidate


def _parse_ratio(val):
    if not val:
        return 0.0
    s = str(val)
    if "/" in s:
        parts = s.split("/", 1)
        try:
            a, b = float(parts[0]), float(parts[1])
            return a / b if a > 0 and b > 0 else 0.0
        except ValueError:
            return 0.0
    try:
        n = float(s)
        return n if n > 0 else 0.0
    except ValueError:
        return 0.0


def probe_media_file(file_path, kind):
    """Probe media file metadata via ffprobe (mirrors FableCut media-lib parseProbe)."""
    info = {}
    p = Path(file_path)
    try:
        info["size"] = p.stat().st_size
    except OSError:
        return info

    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(p)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if res.returncode != 0 or not res.stdout:
            return info
        data = json.loads(res.stdout)
    except Exception:
        return info

    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    v_stream = next((s for s in streams if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    try:
        dur = float(fmt.get("duration") or 0)
        if dur > 0:
            info["duration"] = round(dur, 3)
    except (TypeError, ValueError):
        pass

    try:
        br = int(float(fmt.get("bit_rate") or 0))
        if br > 0:
            info["bitrate"] = br
    except (TypeError, ValueError):
        pass

    if v_stream and kind == "video":
        if v_stream.get("codec_name"):
            info["codec"] = str(v_stream["codec_name"])
        w = int(v_stream.get("width") or 0)
        h = int(v_stream.get("height") or 0)
        rot = 0
        for sd in (v_stream.get("side_data_list") or []):
            if sd.get("rotation") is not None:
                rot = int(float(sd["rotation"]))
                break
        if rot == 0 and (v_stream.get("tags") or {}).get("rotate") is not None:
            try:
                rot = int(float(v_stream["tags"]["rotate"]))
            except (TypeError, ValueError):
                rot = 0
        if abs(rot) % 180 == 90:
            w, h = h, w
        if w > 0 and h > 0:
            info["width"] = w
            info["height"] = h
        fps = _parse_ratio(v_stream.get("avg_frame_rate")) or _parse_ratio(v_stream.get("r_frame_rate"))
        if 0 < fps < 1000:
            info["fps"] = round(fps, 3)

    if a_stream:
        if a_stream.get("codec_name"):
            info["audioCodec"] = str(a_stream["codec_name"])
        ch = int(a_stream.get("channels") or 0)
        if ch > 0:
            info["audioChannels"] = ch
        sr = int(a_stream.get("sample_rate") or 0)
        if sr > 0:
            info["sampleRate"] = sr
    elif v_stream and kind == "video":
        info["audioChannels"] = 0

    return info


def _find_local_media_files(meta, media_dir, json_path=None):
    """Locate local video and audio files in media/<video_id>/ (or legacy flat media/)."""
    media_root = Path(media_dir)
    if not media_root.exists():
        return None, None

    target_video_name = meta.get("video_id", "") or ""
    clean_video_name = target_video_name.removeprefix("upload_") if target_video_name else ""
    target_audio_name = meta.get("voiceover_audio_file", "") or ""

    candidate_dirs = []
    if json_path:
        jp_dir = Path(json_path).resolve().parent
        try:
            if jp_dir.is_relative_to(media_root.resolve()) and jp_dir != media_root.resolve():
                candidate_dirs.append(jp_dir)
        except AttributeError:
            if media_root.resolve() in jp_dir.parents:
                candidate_dirs.append(jp_dir)

    for folder_name in (target_video_name, clean_video_name):
        if folder_name:
            d = media_root / folder_name
            if d.is_dir() and d not in candidate_dirs:
                candidate_dirs.append(d)

    if target_video_name:
        matching_dirs = sorted(d for d in media_root.iterdir() if d.is_dir() and target_video_name.lower() in d.name.lower())
        if len(matching_dirs) == 1 and matching_dirs[0] not in candidate_dirs:
            candidate_dirs.append(matching_dirs[0])
        elif len(matching_dirs) > 1:
            raise ValueError(f"Ambiguous media folders for video_id {target_video_name}: {[d.name for d in matching_dirs]}")

    candidate_dirs.append(media_root)

    found_video = None
    found_audio = None

    for d in candidate_dirs:
        is_dedicated_subdir = d.resolve() != media_root.resolve()
        if not found_video:
            for base_name in dict.fromkeys([n for n in (target_video_name, clean_video_name) if n]):
                for ext in VIDEO_EXTENSIONS:
                    cand = d / f"{base_name}{ext}"
                    if cand.is_file():
                        found_video = cand
                        break
                if found_video:
                    break
            if not found_video and is_dedicated_subdir:
                vids = sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)
                if len(vids) == 1:
                    found_video = vids[0]
                elif len(vids) > 1:
                    exact = [p for p in vids if clean_video_name.lower() in p.name.lower()]
                    if len(exact) == 1:
                        found_video = exact[0]
                    else:
                        raise ValueError(f"Ambiguous source video in {d}: " + ", ".join(p.name for p in vids))

        if not found_audio:
            audio_candidates = []
            if target_audio_name:
                audio_candidates.append(d / target_audio_name)
            for base_name in dict.fromkeys([n for n in (target_video_name, clean_video_name) if n]):
                for ext in AUDIO_EXTENSIONS:
                    audio_candidates.append(d / f"{base_name}_voiceover{ext}")
            for cand in audio_candidates:
                if cand.is_file():
                    found_audio = cand
                    break
            if not found_audio and is_dedicated_subdir:
                auds = sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)
                exact_audio = [p for p in auds if target_audio_name and p.name.lower() == Path(target_audio_name).name.lower()]
                if len(exact_audio) == 1:
                    found_audio = exact_audio[0]
                elif not target_audio_name and len(auds) == 1:
                    found_audio = auds[0]
                elif len(auds) > 1 and target_audio_name and len(exact_audio) != 1:
                    raise ValueError(f"Ambiguous voiceover audio in {d}; set voiceover_audio_file to one of: " + ", ".join(p.name for p in auds))

        if found_video and found_audio:
            break

    return found_video, found_audio


def resolve_media_and_ops(
    meta,
    data_dir=None,
    json_path=None,
    explicit_video_id=None,
    explicit_audio_id=None,
    auto_register=True,
):
    """
    Resolve FableCut mediaIds from project.json or local media/<video_id>/ folder.
    Returns (video_media_id, audio_media_id, media_ops).
    When media exists in fablecut-data/media/<video_id>/ without being registered yet,
    emits addMedia ops using /media/<video_id>/... (avoiding duplicate copies in media/ root).
    """
    data_dir_path = _resolve_data_dir(data_dir)
    media_dir = data_dir_path / "media"
    project_json = data_dir_path / "project.json"

    proj_media = []
    if project_json.exists():
        try:
            proj = load_json(project_json)
            proj_media = proj.get("media", [])
        except Exception:
            proj_media = []

    existing_ids = {m.get("id") for m in proj_media if m.get("id")}
    target_video_name = meta.get("video_id", "") or ""
    clean_video_name = target_video_name.removeprefix("upload_") if target_video_name else ""
    target_audio_name = meta.get("voiceover_audio_file", "") or ""

    local_video, local_audio = _find_local_media_files(meta, media_dir, json_path=json_path)
    local_video_src = _to_media_src(local_video, media_dir) if local_video else None
    local_audio_src = _to_media_src(local_audio, media_dir) if local_audio else None

    def _matches_entry(m, kind):
        m_name = m.get("name", "") or ""
        m_src = unquote(m.get("src", "") or "")
        tokens = [t for t in (target_video_name, clean_video_name) if t]
        if kind == "audio" and target_audio_name:
            tokens.insert(0, target_audio_name)
        if kind == "video" and local_video_src and unquote(local_video_src) == m_src:
            return True
        if kind == "audio" and local_audio_src and unquote(local_audio_src) == m_src:
            return True
        return any(Path(tok).name.lower() == m_name.lower() or Path(tok).name.lower() == Path(m_src).name.lower() or tok.lower() in m_name.lower() or tok.lower() in m_src.lower() for tok in tokens if tok)

    video_media_id = explicit_video_id
    audio_media_id = explicit_audio_id
    media_ops = []

    if not video_media_id:
        matches_v = [m for m in proj_media if m.get("kind") == "video" and _matches_entry(m, "video")]
        if len(matches_v) > 1:
            raise ValueError(f"Ambiguous registered video media for {target_video_name}: {[m.get('id') for m in matches_v]}")
        matched_v = matches_v[0] if matches_v else None
        if not matched_v and not target_video_name:
            matched_v = next((m for m in proj_media if m.get("kind") == "video"), None)

        if matched_v:
            video_media_id = matched_v.get("id")
            cur_file = _src_to_file(matched_v.get("src"), media_dir)
            if (not cur_file or not cur_file.exists()) and local_video_src:
                media_ops.append({
                    "op": "relinkMedia",
                    "id": video_media_id,
                    "src": local_video_src,
                })
        elif auto_register and local_video and local_video_src:
            new_id = "m_fcpipe_" + hashlib.sha1(str(local_video_src).encode("utf-8")).hexdigest()[:10]
            while new_id in existing_ids:
                new_id = f"m_{uuid.uuid4().hex[:7]}"
            existing_ids.add(new_id)
            probed = probe_media_file(local_video, "video")
            media_ops.append({
                "op": "addMedia",
                "media": {
                    "id": new_id,
                    "name": local_video.name,
                    "kind": "video",
                    "src": local_video_src,
                    "folderId": None,
                    **probed,
                },
            })
            video_media_id = new_id

    if not audio_media_id:
        matches_a = [m for m in proj_media if m.get("kind") == "audio" and _matches_entry(m, "audio")]
        if len(matches_a) > 1:
            raise ValueError(f"Ambiguous registered audio media for {target_audio_name or target_video_name}: {[m.get('id') for m in matches_a]}")
        matched_a = matches_a[0] if matches_a else None
        if not matched_a and not target_audio_name and not target_video_name:
            matched_a = next((m for m in proj_media if m.get("kind") == "audio"), None)

        if matched_a:
            audio_media_id = matched_a.get("id")
            cur_file = _src_to_file(matched_a.get("src"), media_dir)
            if (not cur_file or not cur_file.exists()) and local_audio_src:
                media_ops.append({
                    "op": "relinkMedia",
                    "id": audio_media_id,
                    "src": local_audio_src,
                })
        elif auto_register and local_audio and local_audio_src:
            new_id = "m_fcpipe_" + hashlib.sha1(str(local_audio_src).encode("utf-8")).hexdigest()[:10]
            while new_id in existing_ids:
                new_id = f"m_{uuid.uuid4().hex[:7]}"
            existing_ids.add(new_id)
            probed = probe_media_file(local_audio, "audio")
            media_ops.append({
                "op": "addMedia",
                "media": {
                    "id": new_id,
                    "name": local_audio.name,
                    "kind": "audio",
                    "src": local_audio_src,
                    "folderId": None,
                    **probed,
                },
            })
            audio_media_id = new_id

    return video_media_id, audio_media_id, media_ops


def auto_detect_media_ids(meta, data_dir=None):
    """Attempt to detect media IDs from fablecut-data project.json if available."""
    video_id, audio_id, _ = resolve_media_and_ops(meta, data_dir=data_dir, auto_register=False)
    return video_id, audio_id


def build_patch_ops(
    story_data,
    styles_data,
    video_media_id=None,
    audio_media_id=None,
    video_duration=None,
    template_data=None,
    extra_ops=None,
    project_data=None,
    owned_prefix="fcpipe_",
    data_dir=None
):
    segments = story_data.get("segments", [])
    meta = story_data.get("video_metadata", {})
    
    ops = []
    project_data = project_data or {}
    clips = project_data.get("clips", [])
    tracks = project_data.get("tracks", [])
    locked_tracks = set(project_data.get("lockedTracks", []))
    pipeline_clips = [c for c in clips if str(c.get("id", "")).startswith(owned_prefix)]
    for clip in pipeline_clips:
        if clip.get("locked") is True or clip.get("track") in locked_tracks:
            raise ValueError(f"Pipeline-owned clip {clip.get('id')} is locked; refusing to replace it.")
        ops.append({"op": "removeClip", "id": clip["id"]})

    # FableCut's default tracks include V1-V3 and A1-A4. Do not invent track ops.
    
    # Template configuration defaults
    width = 1080
    height = 1920
    fps = 30
    video_volume = 0.0
    text_defaults = {}
    sfx_defaults = {}

    if template_data:
        canvas = template_data.get("canvas", {})
        width = canvas.get("width", 1080)
        height = canvas.get("height", 1920)
        fps = canvas.get("fps", 30)

        layout = template_data.get("layout", {})
        if layout.get("body") == "machine_sound_dominant":
            video_volume = 0.45  # Keep background work / machine ASMR sound audible

        text_defaults = template_data.get("text_defaults", {})
        sfx_defaults = template_data.get("sfx_defaults", {})

    # 1. Project dimensions: Vertical 9:16
    ops.append({
        "op": "setProject",
        "set": {
            "name": meta.get("title", "Shorts 9:16 Video")[:60],
            "width": width,
            "height": height,
            "fps": fps,
            "delivery": {"preset": "youtube-shorts", "audio": {"loudness": -14, "truePeak": -1}}
        }
    })

    # 1b. Prepend media registration/relink ops (e.g. addMedia for media/<video_id>/...)
    if extra_ops:
        ops.extend(extra_ops)
    local_media = {op.get("media", {}).get("id"): op.get("media", {}) for op in (extra_ops or []) if op.get("op") == "addMedia"}
    media_by_id = {m.get("id"): m for m in project_data.get("media", [])}
    media_by_id.update(local_media)
    media_by_src = {m.get("src"): m for m in media_by_id.values() if m.get("src")}

    # Total duration reference
    dur = video_duration or meta.get("duration_seconds", 31.44)
    if not isinstance(dur, (int, float)) or not math.isfinite(dur) or dur <= 0:
        raise ValueError(f"Invalid project duration: {dur}")

    def add_clip(clip):
        clip["id"] = owned_prefix + clip["id"]
        if clip.get("track") in locked_tracks:
            raise ValueError(f"Target track {clip['track']} is locked; refusing to generate clips there.")
        ops.append({"op": "addClip", "clip": clip})

    # Use one source-window clip per segment, split into <=5s retention cuts.
    if video_media_id:
        source = media_by_id.get(video_media_id, {})
        source_duration = float(source.get("duration") or dur)
        cut_index = 0  # SPEC-03: global cut counter for alternating zoom
        for idx, seg in enumerate(segments):
            tr = seg["time_range"]
            start, end = float(tr["start"]), min(float(tr["end"]), dur)
            seg_style = seg.get("style") or {}
            motion = seg_style.get("motion") or {}
            beat_cfg = sfx_defaults.get(seg.get("beat", ""), {})
            template_motion = beat_cfg.get("motion") or {}
            if "speed_ramp" in template_motion and "speed" not in motion:
                motion["speed"] = template_motion["speed_ramp"]
            for motion_key in ("zoom", "shake"):
                if motion_key not in motion and motion_key in template_motion:
                    motion[motion_key] = template_motion[motion_key]
            speed = float(motion.get("speed", seg_style.get("speed", 1.0)) or 1.0)
            if not 0.1 <= speed <= 8:
                raise ValueError(f"speed out of FableCut range [0.1,8]: segments/{idx}/style/motion/speed")
            cursor = start
            part = 0
            while cursor < end - 1e-6:
                length = min(5.0, end - cursor)
                source_in = float(tr["start"]) + (cursor - start) * speed
                source_length = length * speed
                if source_in + source_length > source_duration + 1e-3:
                    raise ValueError(f"Video source window exceeds media duration at segments/{idx}: in={source_in:.3f}, duration={source_length:.3f}, source={source_duration:.3f}")
                filter_aliases = {"contrast-pop": "pop", "natural": "none", "golden-hour": "sunset"}
                filter_name = seg_style.get("filter", beat_cfg.get("filter", "none")) or "none"
                filter_name = filter_aliases.get(filter_name, filter_name)
                filter_valid = {"none", "cinematic", "teal-orange", "noir", "vintage", "faded", "warm", "cold", "pop", "dreamy", "retro", "bw-soft", "cyberpunk", "sunset", "midnight"}
                if filter_name not in filter_valid or (template_allow := (template_data or {}).get("allowed_effects_only", {}).get("filters")) and filter_name not in template_allow:
                    raise ValueError(f"Unsupported/disallowed filter '{filter_name}' at segments/{idx}/style/filter")
                props = {"fit": "cover", "volume": video_volume, "speed": speed, "filterPreset": filter_name}
                # SPEC-03: alternate scale per cut so the <=5s retention cuts read
                # as visible wide/close rhythm. Even cuts use the base zoom (1.0
                # when no explicit zoom); odd cuts punch in 4%. An explicit
                # motion.zoom stays the base for its segment.
                if motion.get("zoom"):
                    base_zoom = float(motion["zoom"])
                    if not 0.5 <= base_zoom <= 4:
                        raise ValueError(f"zoom must be within [0.5,4] at segments/{idx}/style/motion/zoom")
                else:
                    base_zoom = 1.0
                punch = 1.04 if cut_index % 2 == 1 else 1.0
                props["scale"] = round(min(4.0, max(0.5, base_zoom * punch)), 3)
                if motion.get("shake"):
                    props.update({"shake": min(100, max(0, float(motion["shake"]))), "shakeSpeed": 8})
                add_clip({"id": f"v1_seg_{idx+1}_{part+1}", "kind": "video", "mediaId": video_media_id, "track": "V1", "start": round(cursor, 3), "in": round(source_in, 3), "duration": round(length, 3), "name": f"{seg.get('beat','Beat')} footage", "props": props})
                cursor += length
                part += 1
                cut_index += 1

    # 3. Add audio voiceover clip on A1
    if audio_media_id:
        audio_source = media_by_id.get(audio_media_id, {})
        audio_duration = min(dur, float(audio_source.get("duration") or dur))
        add_clip({
                "id": "c_audio_a1",
                "kind": "audio",
                "mediaId": audio_media_id,
                "track": "A1",
                "start": 0,
                "in": 0,
                "duration": round(audio_duration, 3),
                "name": "Voiceover Audio",
                "props": {
                    "volume": 1.0
                }
        })

    # 4. Add text overlays on V2 and apply template / preset styling
    style_aliases = {"BOLD_RED": "IMPACT_RED"}

    last_sfx_start = None
    beat_video_ids = {}
    for idx, seg in enumerate(segments):
        time_range = seg.get("time_range", {})
        start_t = float(time_range.get("start", 0))
        end_t = float(time_range.get("end", start_t + 3))
        
        # Clamp to project duration
        if end_t > dur:
            end_t = dur
        seg_duration = round(max(0.5, end_t - start_t), 3)

        text_overlay = seg.get("text_overlay", {})
        text_content = text_overlay.get("text", "")
        style_key = text_overlay.get("style", "HIGHLIGHT_YELLOW")
        resolved_style = style_aliases.get(style_key, style_key)

        # Fallback to HIGHLIGHT_YELLOW if unknown style
        if resolved_style not in styles_data:
            raise ValueError(f"Unsupported text style '{style_key}' at segments/{idx}/text_overlay/style")

        style_cfg = dict(styles_data.get(resolved_style, {}))
        preset_anim = style_cfg.pop("presetAnimation", None)

        # Override with template text defaults if available
        if text_defaults:
            if "font" in text_defaults:
                style_cfg["font"] = text_defaults["font"]
            if "font_size" in text_defaults:
                style_cfg["fontSize"] = text_defaults["font_size"]
            if "uppercase" in text_defaults:
                style_cfg["uppercase"] = text_defaults["uppercase"]
            if "stroke_width" in text_defaults:
                style_cfg["strokeWidth"] = text_defaults["stroke_width"]
            if "bg_opacity" in text_defaults:
                style_cfg["bgOpacity"] = text_defaults["bg_opacity"]
            if "bg_color" in text_defaults:
                style_cfg["bgColor"] = text_defaults["bg_color"]

        # Override animation from template beat defaults if defined
        beat_name = seg.get("beat", "")
        beat_sfx = sfx_defaults.get(beat_name, {})
        segment_style = seg.get("style") or {}
        for key in ("transition_in", "filter", "text_anim", "preset_anim"):
            if key in segment_style and segment_style[key] is not None and segment_style[key] != "none" and key not in beat_sfx:
                allow_key = {"transition_in": "transitions", "filter": "filters", "text_anim": "text_anim", "preset_anim": "preset_anim"}[key]
                allowed = (template_data or {}).get("allowed_effects_only", {}).get(allow_key)
                if allowed is None or segment_style[key] not in allowed:
                    raise ValueError(f"{key} '{segment_style[key]}' is not explicitly allowlisted by template at segments/{idx}/style/{key}")
        text_anim = segment_style.get("text_anim", beat_sfx.get("text_anim", style_cfg.get("textAnim", "none")))
        if not segment_style.get("text_anim") and beat_sfx.get("text_anim") in {"drop-in", "fade-slide-up"}:
            text_anim = "highlight"
        elif not segment_style.get("text_anim") and beat_sfx.get("text_anim") == "fade":
            text_anim = "none"
        preset_anim = segment_style.get("preset_anim", beat_sfx.get("preset_anim", preset_anim))
        transition_in = segment_style.get("transition_in", beat_sfx.get("transition_in", "none"))
        template_allow = (template_data or {}).get("allowed_effects_only", {})
        if idx == 0:
            transition_in = "none"
            if text_anim in {"clip-reveal", "zoom-in", "rise-mask", "typewriter", "letter-pop", "word-pop", "word-slide"}:
                safe_frame_zero = [name for name in ("highlight", "none", "karaoke", "wave", "bounce", "shake", "font-cut") if name in template_allow.get("text_anim", [])]
                text_anim = safe_frame_zero[0] if safe_frame_zero else "none"
            if preset_anim in {"fade-in", "pop-in", "slide-up-in", "slide-down-in", "slide-left-in", "slide-right-in", "drop-in", "zoom-in", "whip-in", "rise-blur", "draw-on", "fade-out", "pop-out"}:
                preset_anim = None
        if text_anim and text_anim != "none" and template_allow.get("text_anim") and text_anim not in template_allow["text_anim"]:
            raise ValueError(f"text_anim '{text_anim}' for beat {beat_name} is not allowed by template {template_data.get('template_id')}")
        if text_anim and text_anim != "none":
            style_cfg["textAnim"] = text_anim
        else:
            style_cfg["textAnim"] = "none"
        position = segment_style.get("position") or text_overlay.get("position", text_defaults.get("position", "CENTER"))
        pos_y = {"TOP_CENTER": -420, "CENTER": style_cfg.get("y", 0), "LOWER_THIRD": 420}.get(position)
        if pos_y is None:
            raise ValueError(f"Unsupported text position '{position}' at segments/{idx}/text_overlay/position")
        box_w = float(segment_style.get("box_w", style_cfg.get("boxW", 820)) or 820)
        box_h = float(segment_style.get("box_h", style_cfg.get("boxH", 300)) or 300)
        if box_w <= 0 or box_h <= 0 or box_w > 900 or box_h > 1400:
            raise ValueError(f"Text box outside safe-box dimensions at segments/{idx}/style")
        style_cfg.update({"x": min(420-box_w/2, max(-480+box_w/2, float(segment_style.get("x", 0) or 0))),
                          "y": min(640-box_h/2, max(-840+box_h/2, float(segment_style.get("y", pos_y) if segment_style.get("y") is not None else pos_y))),
                          "boxW": box_w, "boxH": box_h, "boxFit": True, "vAlign": "middle"})

        clip_id = f"text_seg_{idx+1}"
        owned_clip_id = owned_prefix + clip_id

        text_clip = {
            "id": clip_id,
            "kind": "text",
            "mediaId": None,
            "track": "V2",
            "start": round(start_t, 3),
            "in": 0,
            "duration": seg_duration,
            "name": f"Text Seg {idx+1}: {beat_name}",
            "props": {
                "text": text_content,
                **style_cfg
            }
        }
        
        add_clip(text_clip)

        # Apply preset animation if specified
        if preset_anim and preset_anim != "none":
            preset_allow = (template_data or {}).get("allowed_effects_only", {}).get("preset_anim")
            if preset_allow is not None and preset_anim not in preset_allow:
                raise ValueError(f"preset_anim '{preset_anim}' for beat {beat_name} is not allowed by template")
            ops.append({
                "op": "applyPreset",
                "id": owned_clip_id,
                "preset": preset_anim,
                "length": min(0.35, round(seg_duration / 2, 2))
            })

        # Apply allowed video-grade properties to the matching pipeline-owned segment clips.
        visual_clips = [c for c in ops if c.get("op") == "addClip" and c["clip"].get("kind") == "video" and c["clip"].get("start", -1) >= start_t and c["clip"].get("start", -1) < end_t]
        beat_video_ids[beat_name] = [c["clip"]["id"] for c in visual_clips]
        for visual in visual_clips:
            video_clip_id = visual["clip"]["id"]
            if video_clip_id.endswith("_1") and transition_in and transition_in != "none" and idx > 0:
                transition_aliases = {"slide": "slide-left", "cut": "none", "flash": "glitch", "whip-pan": "whip"}
                transition_in = transition_aliases.get(transition_in, transition_in)
                allowed_transitions = {"fade", "slide-left", "slide-right", "slide-up", "slide-down", "zoom", "wipe", "wipe-right", "wipe-up", "wipe-down", "iris", "spin", "blur", "whip", "glitch", "pop", "none"}
                permitted_transitions = (template_data or {}).get("allowed_effects_only", {}).get("transitions")
                if transition_in not in allowed_transitions or (permitted_transitions and transition_in not in permitted_transitions and transition_in not in {"slide-left", "slide-right", "slide-up", "slide-down"}):
                    raise ValueError(f"Unsupported transition '{transition_in}' at segments/{idx}/style/transition_in")
                if transition_in != "none":
                    visual["clip"]["transitionIn"] = {"type": transition_in, "duration": 0.35}

        svg_name = segment_style.get("svg_overlay", beat_sfx.get("svg_overlay"))
        if svg_name:
            svg_path = Path(data_dir or _resolve_data_dir()) / "library" / "svg" / Path(svg_name).name
            if not svg_path.is_file():
                raise ValueError(f"SVG overlay not found: {svg_path}")
            svg_src = "/library/svg/" + quote(svg_path.name, safe="")
            existing_svg = media_by_src.get(svg_src)
            if existing_svg:
                svg_media_id = existing_svg["id"]
            else:
                svg_media_id = "m_" + owned_prefix + "svg_" + hashlib.sha1(svg_src.encode("utf-8")).hexdigest()[:8]
                new_media = {"id": svg_media_id, "name": svg_path.name, "kind": "svg", "src": svg_src, "folderId": None}
                ops.append({"op": "addMedia", "media": new_media})
                media_by_src[svg_src] = new_media
            text_y = float(style_cfg.get("y", 0))
            svg_y = -650 + 160 * (idx % 2)
            if position == "TOP_CENTER" and abs(svg_y - text_y) < (box_h / 2 + 120):
                svg_y = min(640 - 120, text_y + box_h / 2 + 140)
            add_clip({"id": f"svg_{idx+1}", "kind": "svg", "mediaId": svg_media_id, "track": "V3", "start": round(start_t, 3), "in": 0, "duration": seg_duration, "name": f"{beat_name} SVG badge", "props": {"fit": "none", "x": 0, "y": svg_y, "scale": 1}})

        cue = seg.get("sfx_cue")
        if cue is not None or "sfx_cue" not in seg:
            cue_id = (cue or {}).get("suggested_sfx") or beat_sfx.get("sfx")
            if not cue_id:
                layout = (template_data or {}).get("layout", {})
                cue_id = layout.get("hook") if idx == 0 else layout.get("payoff") if idx == len(segments) - 1 else layout.get("body")
                if cue_id in {"high_contrast_warning", "ambient_natural_sound", "clean_finish", "machine_sound_dominant", "none"}:
                    cue_id = None
            if cue_id:
                cue_id = Path(cue_id).stem
                sfx_path = Path(data_dir or _resolve_data_dir()) / "library" / "sfx" / f"{cue_id}.wav"
                if not sfx_path.is_file():
                    raise ValueError(f"SFX asset not found: {sfx_path}")
                cue_start = min(end_t - 0.05, start_t + float((cue or {}).get("start_offset", 0.1)))
                if last_sfx_start is not None and cue_start - last_sfx_start < 0.4:
                    cue_start = last_sfx_start + 0.4
                if cue_start < end_t:
                    sfx_src = "/library/sfx/" + quote(sfx_path.name, safe="")
                    sfx_entry = media_by_src.get(sfx_src)
                    if sfx_entry:
                        sfx_media_id = sfx_entry["id"]
                    else:
                        sfx_media_id = "m_" + owned_prefix + "sfx_" + hashlib.sha1(sfx_src.encode("utf-8")).hexdigest()[:8]
                        new_media = {"id": sfx_media_id, "name": sfx_path.name, "kind": "audio", "src": sfx_src, "folderId": None}
                        ops.append({"op": "addMedia", "media": new_media})
                        media_by_src[sfx_src] = new_media
                    add_clip({"id": f"sfx_{idx+1}", "kind": "audio", "mediaId": sfx_media_id, "track": "A2", "start": round(cue_start, 3), "in": 0, "duration": round(end_t-cue_start, 3), "name": f"{beat_name} SFX", "props": {"volume": min(1, max(0, float((cue or {}).get("volume", 0.7)))) * 0.5}})
                    last_sfx_start = cue_start

        per_beat = ((template_data or {}).get("per_beat_style", {}).get(beat_name, {}) if isinstance((template_data or {}).get("per_beat_style"), dict) else {})
        if (template_data or {}).get("template_id") == "before-after" and (segment_style.get("split_screen") or per_beat.get("split_screen") or (template_data or {}).get("per_beat_style", {}).get("split_screen")):
            target_ids = beat_video_ids.get(beat_name, [])
            for video_id in target_ids:
                left = next(c["clip"] for c in ops if c.get("op") == "addClip" and c["clip"].get("id") == video_id)
                left["props"].update({"masks": [{"shape": "rect", "x": 0.25, "y": 0.5, "w": 0.5, "h": 1.0}], "filterPreset": "vintage"})
                right = json.loads(json.dumps(left))
                right["id"] = f"split_after_{idx+1}_{video_id.rsplit('_',1)[-1]}"
                right["name"] = f"{beat_name} after (right)"
                source_offset_delta = max(0.5, right["duration"] * 0.25)
                max_source_in = max(0.0, source_duration - right["duration"])
                distinct_in = min(max_source_in, right["in"] + source_offset_delta)
                if distinct_in <= right["in"] + 1e-6:
                    distinct_in = max(0.0, right["in"] - source_offset_delta)
                right["in"] = round(distinct_in, 3)
                right["props"].update({"masks": [{"shape": "rect", "x": 0.75, "y": 0.5, "w": 0.5, "h": 1.0}], "filterPreset": "teal-orange"})
                add_clip(right)
            labels = ((template_data or {}).get("per_beat_style", {}).get("split_labels", {}) if isinstance((template_data or {}).get("per_beat_style"), dict) else {})
            for side, label, x in (("before", labels.get("left", "BEFORE"), -240), ("after", labels.get("right", "AFTER"), 240)):
                add_clip({"id": f"split_label_{side}_{idx+1}", "kind": "text", "mediaId": None, "track": "V2", "start": round(start_t, 3), "in": 0, "duration": seg_duration, "name": f"{label} split label", "props": {"text": label, "font": "Anton", "fontSize": 54, "color": "#ffffff", "textAnim": "none", "bgColor": "#000000", "bgOpacity": 0.65, "boxW": 300, "boxH": 100, "boxFit": True, "x": x, "y": 500}})

    ops.extend([
        {"op": "setTrack", "id": "A1", "set": {"gain": 0}},
        {"op": "setTrack", "id": "A2", "set": {"gain": -6}},
        {"op": "setFx", "target": "master", "fx": [{"type": "limiter", "ceiling": -1}]},
    ])
    return ops


def main():
    parser = argparse.ArgumentParser(description="Convert commentary JSON to FableCut patch ops")
    parser.add_argument("--json", required=True, help="Path to input commentary json")
    parser.add_argument("--schema", default="schema/input_schema.json", help="Path to schema json")
    parser.add_argument("--presets", default="presets/styles.json", help="Path to styles preset json")
    parser.add_argument("--template", default=None, help="Template ID (e.g. satisfying, shock-hook) or path to template JSON")
    parser.add_argument("--video-id", default=None, help="Registered FableCut mediaId for video")
    parser.add_argument("--audio-id", default=None, help="Registered FableCut mediaId for audio")
    parser.add_argument("--data-dir", default=None, help="Path to fablecut-data directory")
    parser.add_argument("--no-auto-media", action="store_true", help="Do not emit addMedia/relinkMedia ops for local media/<video_id>/ files")
    parser.add_argument("--duration", type=float, default=None, help="Total duration in seconds")
    parser.add_argument("--output", default=None, help="Output file for generated ops JSON")
    parser.add_argument("--owned-prefix", default="fcpipe_", help="Stable prefix used only for pipeline-owned clip IDs")

    args = parser.parse_args()

    # Base directory resolution
    base_dir = Path(__file__).resolve().parent.parent
    schema_path = base_dir / args.schema if not os.path.isabs(args.schema) else Path(args.schema)
    presets_path = base_dir / args.presets if not os.path.isabs(args.presets) else Path(args.presets)
    json_path = Path(args.json)

    if not json_path.exists():
        print(f"ERROR: Input JSON not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    story_data = load_json(json_path)
    
    print(f"Validating {json_path.name} against schema {schema_path.name}...")
    try:
        validate_input_json(story_data, str(schema_path))
        print("Schema validation PASSED.")
    except Exception as e:
        print(f"SCHEMA VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    # Resolve template
    template_id = args.template or story_data.get("template_id") or story_data.get("video_metadata", {}).get("template_id")
    template_data = load_template(template_id, base_dir) if template_id else None
    if template_data:
        print(f"Loaded template: {template_data.get('template_id')} (v{template_data.get('version', '1.0.0')})")

    # Auto detect or register media IDs from media/<video_id>/
    video_media_id, audio_media_id, media_ops = resolve_media_and_ops(
        story_data.get("video_metadata", {}),
        data_dir=args.data_dir,
        json_path=json_path,
        explicit_video_id=args.video_id,
        explicit_audio_id=args.audio_id,
        auto_register=not args.no_auto_media,
    )
    if media_ops:
        print(f"Generated {len(media_ops)} media op(s): {[op['op'] for op in media_ops]}")

    styles_data = load_json(presets_path)
    ops = build_patch_ops(
        story_data,
        styles_data,
        video_media_id=video_media_id,
        audio_media_id=audio_media_id,
        video_duration=args.duration,
        template_data=template_data,
        extra_ops=media_ops,
        project_data=load_json(_resolve_data_dir(args.data_dir) / "project.json") if (_resolve_data_dir(args.data_dir) / "project.json").exists() else {},
        data_dir=args.data_dir,
        owned_prefix=args.owned_prefix,
    )

    out_content = json.dumps(ops, indent=2, ensure_ascii=False)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_content)
        print(f"Generated {len(ops)} patch ops written to: {out_path}")
    else:
        print(out_content)


if __name__ == "__main__":
    main()
