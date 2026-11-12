#!/usr/bin/env python3
"""
cleanup.py - Safe Batch Cleanup for FableCut Shorts Pipeline
Cleans temporary intermediates in youtube-analyst-niches-forest/temp/ and
per-video source folders in fablecut-data/media/<video_id>/ (plus disposable caches),
while strictly protecting final rendered outputs in fablecut-data/exports/,
assets in fablecut-data/library/, and FableCut project data in projects/.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import unquote

DEFAULT_BUNDLE_DIR = Path(__file__).resolve().parent
DEFAULT_WORKSPACE_DIR = DEFAULT_BUNDLE_DIR.parent
DEFAULT_ANALYST_DIR = DEFAULT_WORKSPACE_DIR / "youtube-analyst-niches-forest"
DEFAULT_DATA_DIR = Path(os.environ.get("FABLECUT_DATA_DIR") or (DEFAULT_WORKSPACE_DIR / "fablecut-data"))


def format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    for unit in ("KB", "MB", "GB", "TB"):
        num_bytes /= 1024.0
        if num_bytes < 1024.0:
            return f"{num_bytes:.2f} {unit}"
    return f"{num_bytes:.2f} PB"


def get_path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for root, _, files in os.walk(path):
        for fname in files:
            fp = Path(root) / fname
            try:
                total += fp.stat().st_size
            except OSError:
                pass
    return total


def proxy_base_prefix(file_path: Path) -> Optional[str]:
    """Mirror FableCut proxy.js baseName(file) to match exact proxy cache files."""
    try:
        st = file_path.stat()
        resolved = str(file_path.resolve())
        mtime_ms = int(st.st_mtime_ns / 1_000_000 + 0.5)
        key = f"{resolved}|{st.st_size}|{mtime_ms}"
        h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        stem = re.sub(r"[^A-Za-z0-9_\-]+", "_", file_path.stem)[:40] or "media"
        return f"{stem}-{h}-"
    except OSError:
        return None


def collect_open_project_media_paths(data_dir: Path) -> Tuple[Set[Path], Set[Path]]:
    """
    Read fablecut-data/project.json to identify media files and top-level
    media/<video_id>/ folders referenced by the currently open project.
    """
    protected_files: Set[Path] = set()
    protected_folders: Set[Path] = set()
    project_json = data_dir / "project.json"
    media_root = (data_dir / "media").resolve()

    if not project_json.exists():
        return protected_files, protected_folders

    try:
        doc = json.loads(project_json.read_text(encoding="utf-8-sig"))
    except Exception:
        return protected_files, protected_folders

    for m in doc.get("media", []):
        src = str(m.get("src") or "")
        if not src.startswith("/media/"):
            continue
        rel = unquote(src.split("?", 1)[0][len("/media/"):]).strip("/")
        if not rel:
            continue
        candidate = (media_root / rel).resolve()
        try:
            if not candidate.is_relative_to(media_root):
                continue
        except AttributeError:
            if media_root not in candidate.parents:
                continue
        protected_files.add(candidate)
        rel_parts = candidate.relative_to(media_root).parts
        if len(rel_parts) >= 2:
            protected_folders.add((media_root / rel_parts[0]).resolve())

    return protected_files, protected_folders


def _latest_mtime(path: Path) -> float:
    try:
        mtime = path.stat().st_mtime
        if path.is_dir():
            for p in path.rglob("*"):
                try:
                    mtime = max(mtime, p.stat().st_mtime)
                except OSError:
                    pass
        return mtime
    except OSError:
        return 0.0


def is_older_than_days(path: Path, days: Optional[float], now_ts: float) -> bool:
    if days is None or days <= 0:
        return True
    mtime = _latest_mtime(path)
    if mtime <= 0:
        return False
    age_days = (now_ts - mtime) / 86400.0
    return age_days >= days


def gather_cleanup_plan(
    analyst_dir: Path,
    data_dir: Path,
    video_ids: Optional[List[str]] = None,
    keep_latest: int = 0,
    older_than_days: Optional[float] = None,
    include_active: bool = False,
    skip_cache: bool = False,
) -> Dict[str, List[Dict]]:
    now_ts = time.time()
    temp_dir = analyst_dir / "temp"
    media_dir = data_dir / "media"
    proxies_dir = data_dir / "analysis" / "proxies"
    frames_dir = data_dir / "analysis" / "frames"

    protected_files, protected_folders = (
        (set(), set()) if include_active else collect_open_project_media_paths(data_dir)
    )

    plan: Dict[str, List[Dict]] = {
        "delete": [],
        "skipped": [],
    }

    normalized_targets: Set[str] = set()
    if video_ids:
        for vid in video_ids:
            for item in vid.split(","):
                v = item.strip()
                if v:
                    normalized_targets.add(v)
                    normalized_targets.add(v.removeprefix("upload_"))
                    if not v.startswith("upload_"):
                        normalized_targets.add(f"upload_{v}")

    # 1. Temp files in youtube-analyst-niches-forest/temp/
    if temp_dir.is_dir():
        for entry in sorted(temp_dir.iterdir(), key=lambda p: p.name):
            if entry.name == ".gitkeep":
                continue
            if normalized_targets:
                if not any(tok in entry.name for tok in normalized_targets):
                    continue
            if not is_older_than_days(entry, older_than_days, now_ts):
                plan["skipped"].append({
                    "category": "TEMP",
                    "path": entry,
                    "size": get_path_size(entry),
                    "reason": f"newer than {older_than_days} day(s)",
                })
                continue
            plan["delete"].append({
                "category": "TEMP",
                "path": entry,
                "size": get_path_size(entry),
            })

    # 2. Media folders & legacy flat files in fablecut-data/media/
    deleted_media_files: List[Path] = []
    if media_dir.is_dir():
        entries = list(media_dir.iterdir())
        subdirs = [p for p in entries if p.is_dir()]
        flat_files = [p for p in entries if p.is_file()]

        # Sort subdirs newest-first by latest mtime for --keep-latest
        subdirs_sorted = sorted(subdirs, key=_latest_mtime, reverse=True)
        keep_set: Set[Path] = set()
        if not normalized_targets and keep_latest > 0:
            keep_set = {p.resolve() for p in subdirs_sorted[:keep_latest]}

        for folder in subdirs_sorted:
            resolved_folder = folder.resolve()
            if normalized_targets and folder.name not in normalized_targets:
                continue
            if resolved_folder in keep_set:
                plan["skipped"].append({
                    "category": "MEDIA_DIR",
                    "path": folder,
                    "size": get_path_size(folder),
                    "reason": f"kept by --keep-latest {keep_latest}",
                })
                continue
            if resolved_folder in protected_folders:
                plan["skipped"].append({
                    "category": "MEDIA_DIR",
                    "path": folder,
                    "size": get_path_size(folder),
                    "reason": "referenced by open project.json (use --include-active to override)",
                })
                continue
            if not is_older_than_days(folder, older_than_days, now_ts):
                plan["skipped"].append({
                    "category": "MEDIA_DIR",
                    "path": folder,
                    "size": get_path_size(folder),
                    "reason": f"newer than {older_than_days} day(s)",
                })
                continue
            for f in folder.rglob("*"):
                if f.is_file():
                    deleted_media_files.append(f)
            plan["delete"].append({
                "category": "MEDIA_DIR",
                "path": folder,
                "size": get_path_size(folder),
            })

        for f in sorted(flat_files, key=lambda p: p.name):
            resolved_f = f.resolve()
            if normalized_targets:
                if not any(tok in f.name for tok in normalized_targets):
                    continue
            if resolved_f in protected_files:
                plan["skipped"].append({
                    "category": "MEDIA_FILE",
                    "path": f,
                    "size": get_path_size(f),
                    "reason": "referenced by open project.json (use --include-active to override)",
                })
                continue
            if not is_older_than_days(f, older_than_days, now_ts):
                plan["skipped"].append({
                    "category": "MEDIA_FILE",
                    "path": f,
                    "size": get_path_size(f),
                    "reason": f"newer than {older_than_days} day(s)",
                })
                continue
            deleted_media_files.append(f)
            plan["delete"].append({
                "category": "MEDIA_FILE",
                "path": f,
                "size": get_path_size(f),
            })

    # 3. Disposable analysis caches (proxies/ & frames/)
    if not skip_cache:
        if proxies_dir.is_dir():
            if normalized_targets:
                prefixes = [p for p in (proxy_base_prefix(f) for f in deleted_media_files) if p]
                for pfile in sorted(proxies_dir.iterdir(), key=lambda p: p.name):
                    if not pfile.is_file():
                        continue
                    matched = any(pfile.name.startswith(pref) for pref in prefixes) or any(
                        tok in pfile.name for tok in normalized_targets
                    )
                    if matched:
                        plan["delete"].append({
                            "category": "PROXY",
                            "path": pfile,
                            "size": get_path_size(pfile),
                        })
            else:
                protected_proxy_prefixes = {
                    p for p in (proxy_base_prefix(f) for f in protected_files if f.exists()) if p
                }
                for pfile in sorted(proxies_dir.iterdir(), key=lambda p: p.name):
                    if not pfile.is_file():
                        continue
                    if any(pfile.name.startswith(pref) for pref in protected_proxy_prefixes):
                        plan["skipped"].append({
                            "category": "PROXY",
                            "path": pfile,
                            "size": get_path_size(pfile),
                            "reason": "proxy for open project.json media",
                        })
                        continue
                    if not is_older_than_days(pfile, older_than_days, now_ts):
                        continue
                    plan["delete"].append({
                        "category": "PROXY",
                        "path": pfile,
                        "size": get_path_size(pfile),
                    })

        if frames_dir.is_dir() and not normalized_targets:
            for fitem in sorted(frames_dir.iterdir(), key=lambda p: p.name):
                if not is_older_than_days(fitem, older_than_days, now_ts):
                    continue
                plan["delete"].append({
                    "category": "FRAMES",
                    "path": fitem,
                    "size": get_path_size(fitem),
                })

    return plan


def execute_cleanup(plan: Dict[str, List[Dict]], dry_run: bool = True) -> Tuple[int, int, List[str]]:
    deleted_count = 0
    freed_bytes = 0
    errors: List[str] = []

    for item in plan["delete"]:
        p: Path = item["path"]
        sz: int = item["size"]
        if dry_run:
            deleted_count += 1
            freed_bytes += sz
            continue
        try:
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
            deleted_count += 1
            freed_bytes += sz
        except Exception as err:
            errors.append(f"{p}: {err}")

    return deleted_count, freed_bytes, errors


def main():
    parser = argparse.ArgumentParser(
        description="Safe batch cleanup for youtube-analyst-niches-forest/temp and fablecut-data/media"
    )
    parser.add_argument("--analyst-dir", default=str(DEFAULT_ANALYST_DIR), help="Path to youtube-analyst-niches-forest")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Path to fablecut-data")
    parser.add_argument("--video-id", action="append", default=None, help="Target specific video_id(s) only")
    parser.add_argument("--keep-latest", type=int, default=0, help="Keep N newest video folders in media/")
    parser.add_argument("--older-than-days", type=float, default=None, help="Only delete items older than N days")
    parser.add_argument("--include-active", action="store_true", help="Also allow deleting media used in current project.json")
    parser.add_argument("--skip-cache", action="store_true", help="Keep analysis/proxies and analysis/frames")
    parser.add_argument("--dry-run", action="store_true", help="Preview items without deleting")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt and delete immediately")

    args = parser.parse_args()
    analyst_dir = Path(args.analyst_dir).resolve()
    data_dir = Path(args.data_dir).resolve()

    plan = gather_cleanup_plan(
        analyst_dir=analyst_dir,
        data_dir=data_dir,
        video_ids=args.video_id,
        keep_latest=max(0, args.keep_latest),
        older_than_days=args.older_than_days,
        include_active=args.include_active,
        skip_cache=args.skip_cache,
    )

    print("=" * 68)
    print("FABLECUT PIPELINE BATCH CLEANUP")
    print("=" * 68)
    print(f"Temp root   : {analyst_dir / 'temp'}")
    print(f"Media root  : {data_dir / 'media'}")
    print(f"Protected   : {data_dir / 'exports'}, {data_dir / 'library'}, {data_dir / 'projects'}, {data_dir / 'project.json'}")
    print("-" * 68)

    if plan["skipped"]:
        print(f"Skipped / Protected ({len(plan['skipped'])}):")
        for item in plan["skipped"]:
            print(f"  [SKIP:{item['category']}] {item['path']} ({format_bytes(item['size'])}) - {item['reason']}")
        print("-" * 68)

    if not plan["delete"]:
        print("Nothing to clean up.")
        return

    total_target_bytes = sum(item["size"] for item in plan["delete"])
    action_label = "WOULD DELETE" if args.dry_run else "TARGET"
    print(f"Items to remove ({len(plan['delete'])}, {format_bytes(total_target_bytes)}):")
    for item in plan["delete"]:
        print(f"  [{action_label}:{item['category']}] {item['path']} ({format_bytes(item['size'])})")

    if args.dry_run:
        print("-" * 68)
        print(f"DRY RUN COMPLETE: {len(plan['delete'])} item(s), {format_bytes(total_target_bytes)} would be freed.")
        return

    if not args.yes:
        reply = input(f"\nProceed with deleting {len(plan['delete'])} item(s) ({format_bytes(total_target_bytes)})? [y/N]: ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted. Nothing was deleted.")
            return

    deleted_count, freed_bytes, errors = execute_cleanup(plan, dry_run=False)
    print("-" * 68)
    print(f"CLEANUP COMPLETE: deleted {deleted_count} item(s), freed {format_bytes(freed_bytes)}.")
    if errors:
        print("Errors encountered:", file=sys.stderr)
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
