import logging
import sys
import subprocess
from pathlib import Path
from src.core.config import settings

logger = logging.getLogger(__name__)

class VideoDownloader:
    """Tải video từ link YouTube Shorts / TikTok / Reels về máy bằng yt-dlp"""

    def __init__(self, temp_dir: Path = None):
        self.temp_dir = temp_dir or settings.TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def download_video(self, url: str) -> str:
        """Tải video MP4 chất lượng tối ưu cho Short (720p/1080p)"""
        output_template = str(self.temp_dir / "%(id)s.%(ext)s")
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", output_template,
            "--no-playlist",
            url
        ]

        logger.info(f"Downloading video from {url}...")
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Tìm file mp4 vừa tải về trong thư mục temp
        for line in res.stdout.splitlines():
            if "[Merger] Merging formats into" in line or "[download] Destination:" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    filepath = parts[-1].strip().strip('"')
                    if Path(filepath).exists():
                        return filepath
                        
        # Fallback tìm file mới nhất trong temp_dir
        mp4_files = sorted(self.temp_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        if mp4_files:
            return str(mp4_files[0])
            
        raise RuntimeError("Failed to locate downloaded video file from yt-dlp")
