import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
from src.core.config import settings
from src.models.schemas import VisualActionTimeline, CapCutCommentaryInterchange

DB_PATH = settings.DATA_DIR / "commentary_studio.db"

class DatabaseManager:
    """Quản lý lưu trữ SQLite cục bộ cho Visual Timelines và Kịch bản CapCut"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS visual_timelines (
                    video_id TEXT PRIMARY KEY,
                    duration_seconds REAL,
                    subject_matter TEXT,
                    timeline_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS commentary_scripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT,
                    skill_id TEXT,
                    language TEXT,
                    script_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(video_id) REFERENCES visual_timelines(video_id)
                );
            """)
            conn.commit()

    def save_visual_timeline(self, timeline: VisualActionTimeline):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO visual_timelines (video_id, duration_seconds, subject_matter, timeline_json)
                VALUES (?, ?, ?, ?);
            """, (
                timeline.video_id,
                timeline.duration_seconds,
                timeline.subject_matter,
                timeline.model_dump_json()
            ))
            conn.commit()

    def get_visual_timeline(self, video_id: str) -> Optional[VisualActionTimeline]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT timeline_json FROM visual_timelines WHERE video_id = ?;", (video_id,))
            row = cursor.fetchone()
            if row:
                return VisualActionTimeline(**json.loads(row["timeline_json"]))
        return None

    def save_commentary_script(self, script: CapCutCommentaryInterchange) -> int:
        """Lưu thêm 1 phiên bản kịch bản (append, không ghi đè). Trả về id dòng mới."""
        meta = script.video_metadata
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO commentary_scripts (video_id, skill_id, language, script_json)
                VALUES (?, ?, ?, ?);
            """, (
                meta.video_id,
                meta.skill_applied,
                meta.language,
                script.model_dump_json()
            ))
            conn.commit()
            return cursor.lastrowid

    def get_latest_script(self, video_id: str, skill_id: Optional[str] = None) -> Optional[CapCutCommentaryInterchange]:
        with self._get_connection() as conn:
            query = "SELECT script_json FROM commentary_scripts WHERE video_id = ?"
            params = [video_id]
            if skill_id:
                query += " AND skill_id = ?"
                params.append(skill_id)
            query += " ORDER BY id DESC LIMIT 1;"
            
            cursor = conn.execute(query, tuple(params))
            row = cursor.fetchone()
            if row:
                return CapCutCommentaryInterchange(**json.loads(row["script_json"]))
        return None

db = DatabaseManager()
