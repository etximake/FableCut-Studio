#!/usr/bin/env python3
"""Validate interchange fixtures, generated patch ops, and optional rendered media."""
import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT.parent / "fablecut-data" / "library" / "fonts"
VISIBLE_TEXT_ANIMS = {"none", "highlight", "karaoke", "wave", "bounce", "shake", "font-cut"}
HIDDEN_TEXT_ANIMS = {"clip-reveal", "zoom-in", "rise-mask", "typewriter", "letter-pop", "word-pop", "word-slide"}
IN_PRESETS = {"fade-in", "pop-in", "slide-up-in", "slide-down-in", "slide-left-in", "slide-right-in", "drop-in", "zoom-in", "spin-in", "whip-in", "rise-blur", "draw-on"}


def validate_input(path, schema, strict=None):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if jsonschema is None:
        raise RuntimeError("jsonschema is required for QA; no partial validation is performed")
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(data), key=lambda e: list(map(str, e.path)))
    if errors:
        e = errors[0]
        raise ValueError(f"{path.name}: {'/'.join(map(str,e.path))}: {e.message}")
    meta = data.get("video_metadata", {})
    is_strict = bool(data.get("template_id") or meta.get("template_id")) if strict is None else strict
    prev = None
    duration = float(meta["duration_seconds"])
    for i, seg in enumerate(data["segments"]):
        start, end = seg["time_range"]["start"], seg["time_range"]["end"]
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
            raise ValueError(f"{path.name}: invalid time range at segments/{i}/time_range")
        if is_strict and end > duration:
            raise ValueError(f"{path.name}: end {end} exceeds duration {duration} at segments/{i}")
        if is_strict and prev is not None and abs(start-prev) > 0.01:
            raise ValueError(f"{path.name}: timeline gap at segments/{i}, expected {prev}, got {start}")
        if prev is not None and start < prev - 0.01:
            raise ValueError(f"{path.name}: overlapping segments at {i}")
        prev = end
    return data


def validate_ops(path):
    ops = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(ops, list):
        raise ValueError("patch ops must be a JSON array")
    clips = {}
    sfx = []
    transitions_by_beat = {}
    for i, op in enumerate(ops):
        if not isinstance(op, dict) or not isinstance(op.get("op"), str):
            raise ValueError(f"ops/{i}: malformed operation")
        if op["op"] == "addClip":
            c = op.get("clip", {})
            if not c.get("id") or not c.get("track") or not isinstance(c.get("start"), (int,float)) or not isinstance(c.get("duration"), (int,float)) or c["duration"] <= 0:
                raise ValueError(f"ops/{i}: malformed addClip")
            if c["id"] in clips:
                raise ValueError(f"ops/{i}: duplicate clip id {c['id']}")
            clips[c["id"]] = c
            if c.get("track") == "A2": sfx.append(c)
            if c.get("kind") == "video" and c.get("transitionIn"):
                beat = c.get("name", "").removesuffix(" footage")
                transitions_by_beat[beat] = transitions_by_beat.get(beat, 0) + 1
    first_text = min((c for c in clips.values() if c.get("kind") == "text"), key=lambda c:c["start"], default=None)
    if first_text:
        p = first_text.get("props", {})
        if p.get("textAnim", "none") not in VISIBLE_TEXT_ANIMS:
            raise ValueError("first text clip animation is not visible at Frame 0")
        if first_text.get("transitionIn", {}).get("type") not in (None, "none"):
            raise ValueError("first text clip has a transition at Frame 0")
        bw, bh = p.get("boxW", 0), p.get("boxH", 0)
        x, y = p.get("x", 0), p.get("y", 0)
        if bw and (x-bw/2 < -480-1e-6 or x+bw/2 > 420+1e-6):
            raise ValueError("first text box exceeds horizontal safe box")
        if bh and (y-bh/2 < -840-1e-6 or y+bh/2 > 640+1e-6):
            raise ValueError("first text box exceeds vertical safe box")
    for c in clips.values():
        if c.get("kind") == "video" and c["duration"] > 5.001:
            raise ValueError(f"video clip {c['id']} exceeds 5 seconds")
    if any(count > 1 for count in transitions_by_beat.values()):
        raise ValueError("transitionIn must appear only on the first video cut of each beat")
    text_boxes = [c for c in clips.values() if c.get("kind") == "text" and c.get("track") == "V2"]
    split_after = [c for c in clips.values() if c.get("id", "").startswith("fcpipe_split_after_")]
    if split_after:
        labels = [c.get("props", {}).get("text") for c in text_boxes if c.get("id", "").startswith("fcpipe_split_label_")]
        if "BEFORE" not in labels or "AFTER" not in labels:
            raise ValueError("before-after split screen requires visible BEFORE and AFTER labels")
        originals = [c for c in clips.values() if c.get("kind") == "video" and not c.get("id", "").startswith("fcpipe_split_after_")]
        for right in split_after:
            matching = next((c for c in originals if c["start"] == right["start"] and c["duration"] == right["duration"]), None)
            if matching is None or abs(right.get("in", 0) - matching.get("in", 0)) <= 1e-6:
                raise ValueError(f"before-after right-side clip {right['id']} must use a distinct source offset")
    for svg in (c for c in clips.values() if c.get("kind") == "svg" and c.get("track") == "V3"):
        if not (svg.get("props", {}).get("y", 0) < 0):
            continue
        for text in text_boxes:
            if text["start"] < svg["start"] + svg["duration"] and svg["start"] < text["start"] + text["duration"]:
                p = text.get("props", {})
                if abs(p.get("y", 0) - svg["props"].get("y", 0)) < p.get("boxH", 0) / 2 + 120:
                    raise ValueError(f"V3 SVG {svg['id']} overlaps the TOP_CENTER V2 text box {text['id']}")
    for clip in sfx:
        if clip["duration"] <= 0:
            raise ValueError(f"SFX clip {clip['id']} is clipped to an empty duration")
    sfx.sort(key=lambda c:c["start"])
    for a,b in zip(sfx,sfx[1:]):
        if b["start"]-a["start"] < 0.4-1e-6:
            raise ValueError(f"SFX cues overlap within 0.4s: {a['id']} and {b['id']}")
    return ops


def validate_template_assets():
    registry_path = ROOT / "presets" / "templates" / "index.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if not FONT_DIR.is_dir():
        raise ValueError(f"font library not found: {FONT_DIR}")
    available_fonts = {p.stem for p in FONT_DIR.glob("*.woff2")}
    for item in registry.get("templates", []):
        template_path = ROOT / "presets" / "templates" / Path(item["file"]).name
        template = json.loads(template_path.read_text(encoding="utf-8"))
        font = template.get("text_defaults", {}).get("font")
        if font and font not in available_fonts:
            raise ValueError(f"template {item['template_id']} font {font!r} has no matching .woff2 asset")
    styles = json.loads((ROOT / "presets" / "styles.json").read_text(encoding="utf-8"))
    for style_id, style in styles.items():
        font = style.get("font")
        if font and font not in available_fonts:
            raise ValueError(f"style {style_id} font {font!r} has no matching .woff2 asset")


def validate_media(path, duration=None):
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], capture_output=True, text=True)
    if probe.returncode:
        raise ValueError(f"ffprobe failed: {probe.stderr.strip()}")
    doc=json.loads(probe.stdout)
    video=next((s for s in doc.get("streams",[]) if s.get("codec_type")=="video"),None)
    audio=next((s for s in doc.get("streams",[]) if s.get("codec_type")=="audio"),None)
    if not video or (video.get("width"),video.get("height")) != (1080,1920):
        raise ValueError("render must contain 1080x1920 video")
    if video.get("pix_fmt") != "yuv420p": raise ValueError(f"unexpected pixel format: {video.get('pix_fmt')}")
    if audio and (audio.get("codec_name") != "aac" or str(audio.get("sample_rate")) != "48000"):
        raise ValueError("audio must be AAC at 48 kHz")
    actual=float(doc.get("format",{}).get("duration",0))
    if duration is not None and abs(actual-duration)>0.5: raise ValueError(f"render duration {actual:.3f}s differs from expected {duration:.3f}s")
    loud=subprocess.run(["ffmpeg","-hide_banner","-nostats","-i",str(path),"-af","ebur128=peak=true","-f","null","-"],capture_output=True,text=True)
    text=loud.stderr
    integrated=re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS",text)
    peaks=re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS",text)
    if integrated and abs(float(integrated[-1])+14)>1.5: raise ValueError(f"integrated loudness {integrated[-1]} LUFS outside -14±1.5")
    if peaks and float(peaks[-1])>-1.0: raise ValueError(f"true peak {peaks[-1]} dBFS exceeds -1.0")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path)
    parser.add_argument("--ops",type=Path)
    parser.add_argument("--render",type=Path)
    parser.add_argument("--duration",type=float)
    parser.add_argument("--all-examples",action="store_true",help="Read-only validation of examples/*.json")
    args=parser.parse_args()
    schema=json.loads((ROOT/"schema/input_schema.json").read_text(encoding="utf-8-sig"))
    try:
        if args.all_examples:
            validate_template_assets()
            for p in sorted((ROOT/"examples").glob("*.json")):
                validate_input(p,schema,strict=False if "legacy" in p.name or "upload_" in p.name else None)
                print(f"PASS input {p.name}")
        if args.input:
            validate_input(args.input,schema)
            print(f"PASS input {args.input}")
        if args.ops:
            validate_ops(args.ops)
            print(f"PASS ops {args.ops}")
        if args.render:
            validate_media(args.render,args.duration)
            print(f"PASS render {args.render}")
        if not (args.all_examples or args.input or args.ops or args.render): parser.error("supply --all-examples, --input, --ops, or --render")
    except Exception as exc:
        print(f"FAIL: {exc}",file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
