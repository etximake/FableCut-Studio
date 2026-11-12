import os
import re
from pathlib import Path
from typing import Optional
from dotenv import dotenv_values, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

def clean_env_value(val: Optional[str]) -> str:
    """Loại bỏ inline comment (# ...) và khoảng trắng thừa từ giá trị trong .env"""
    if val is None:
        return ""
    cleaned = re.split(r"\s+#", val.strip())[0].strip()
    return cleaned.strip('"\'')

class DynamicSettings:
    """
    Quản lý cấu hình linh hoạt (Dynamic Config Provider).
    Tự động đọc các giá trị mới nhất từ file .env theo thời gian thực (Hot-Reload).
    """
    APP_NAME: str = "AI Video Commentary & CapCut Engine"
    VERSION: str = "2.0.0"
    
    DATA_DIR: Path = BASE_DIR / "data"
    TEMP_DIR: Path = BASE_DIR / "temp"
    ASSETS_DIR: Path = BASE_DIR / "assets"
    SFX_DIR: Path = BASE_DIR / "assets" / "sfx_library"

    def __init__(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        self.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        load_dotenv(dotenv_path=ENV_PATH, override=True)

    @property
    def EXPORTS_DIR(self) -> Path:
        custom_dir = self.get_var("EXPORTS_DIR") or self.get_var("FABLECUT_MEDIA_DIR")
        if custom_dir:
            p = Path(custom_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p
        fallback = BASE_DIR / "exports"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def sanitize_video_id(self, video_id: str) -> str:
        """Chuẩn hóa video_id thành tên thư mục an toàn trên Windows/POSIX"""
        safe_id = re.sub(r'[<>:"/\\|?*]', "_", str(video_id or "")).strip(" .")
        safe_id = safe_id.replace("..", "_")
        return safe_id or "video"

    def get_video_export_dir(
        self,
        video_id: str,
        base_dir: Optional[Path] = None,
        create: bool = True
    ) -> Path:
        """Trả về thư mục con riêng cho từng video: EXPORTS_DIR/<video_id>/"""
        root = base_dir or self.EXPORTS_DIR
        video_dir = root / self.sanitize_video_id(video_id)
        if create:
            video_dir.mkdir(parents=True, exist_ok=True)
        return video_dir

    def _get_active_env(self) -> dict:
        env_dict = {}
        if ENV_PATH.exists():
            env_dict = dotenv_values(ENV_PATH)
        return env_dict

    def get_var(self, key: str, default: str = "") -> str:
        env_dict = self._get_active_env()
        val = env_dict.get(key)
        if val is None:
            val = os.getenv(key, default)
        return clean_env_value(str(val) if val is not None else default)

    @property
    def GEMINI_API_KEY(self) -> str:
        return self.get_var("GEMINI_API_KEY", "")

    @property
    def OPENAI_API_KEY(self) -> str:
        return self.get_var("OPENAI_API_KEY", "")

    @property
    def OPENAI_BASE_URL(self) -> Optional[str]:
        url = self.get_var("OPENAI_BASE_URL") or self.get_var("CUSTOM_AI_BASE_URL")
        return url if url else None

    @property
    def DEFAULT_AI_PROVIDER(self) -> str:
        provider = self.get_var("DEFAULT_AI_PROVIDER", "openai").lower()
        return provider if provider else "openai"

    @property
    def IS_GEMINI(self) -> bool:
        return self.DEFAULT_AI_PROVIDER == "gemini"

    @property
    def BACKUP_AI_PROVIDER(self) -> str:
        return self.get_var("BACKUP_AI_PROVIDER", "").lower()

    @property
    def BACKUP_OPENAI_API_KEY(self) -> str:
        return self.get_var("BACKUP_OPENAI_API_KEY", "")

    @property
    def BACKUP_OPENAI_BASE_URL(self) -> Optional[str]:
        return self.get_var("BACKUP_OPENAI_BASE_URL") or None

    @property
    def BACKUP_GEMINI_API_KEY(self) -> str:
        return self.get_var("BACKUP_GEMINI_API_KEY", "")

    @property
    def DEFAULT_VISION_MODEL(self) -> str:
        # Tự động chọn model phù hợp nếu chưa chỉ định rõ
        model = self.get_var("DEFAULT_VISION_MODEL")
        if not model:
            if self.IS_GEMINI:
                return "gemini-2.0-flash"
            return self.get_var("DEFAULT_FAST_MODEL", "gpt-4o-mini")
        return model

    @property
    def DEFAULT_TEXT_MODEL(self) -> str:
        model = self.get_var("DEFAULT_TEXT_MODEL")
        if not model:
            if self.IS_GEMINI:
                return "gemini-2.0-flash"
            return self.get_var("DEFAULT_FAST_MODEL", "gpt-4o-mini")
        return model

    @property
    def BACKUP_VISION_MODEL(self) -> str:
        return self.get_var("BACKUP_VISION_MODEL") or self.get_var("BACKUP_FAST_MODEL", "gpt-4o-mini")

    @property
    def BACKUP_TEXT_MODEL(self) -> str:
        return self.get_var("BACKUP_TEXT_MODEL") or self.get_var("BACKUP_FAST_MODEL", "gpt-4o-mini")

    @property
    def PREFERRED_LANGUAGE(self) -> str:
        return self.get_var("PREFERRED_LANGUAGE", "vi")

    @property
    def DEFAULT_COMMENTARY_SKILL(self) -> str:
        return self.get_var("DEFAULT_COMMENTARY_SKILL", "curiosity-explainer")

settings = DynamicSettings()
