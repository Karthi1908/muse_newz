from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")


class Settings:
    """Centralized settings where LLM API paths and model identifiers come strictly from .env."""

    def __init__(self) -> None:
        # LLM API Path & Models (Loaded exclusively from .env)
        self.LLM_API_BASE_URL: str = os.getenv("LLM_API_BASE_URL", "").rstrip("/")
        self.MODEL_API_KEY: str = os.getenv("MODEL_API_KEY", "")
        self.MUSE_TEXT_MODEL: str = os.getenv("MUSE_TEXT_MODEL", "")
        self.MUSE_IMAGE_MODEL: str = os.getenv("MUSE_IMAGE_MODEL", "")
        self.MUSE_VOICE_MODEL: str = os.getenv("MUSE_VOICE_MODEL", "")
        self.MUSE_SAM_MODEL: str = os.getenv("MUSE_SAM_MODEL", "sam-3.1")

        # Endpoint sub-paths from .env
        self.LLM_CHAT_COMPLETIONS_PATH: str = os.getenv("LLM_CHAT_COMPLETIONS_PATH", "/chat/completions")
        self.LLM_RESPONSES_PATH: str = os.getenv("LLM_RESPONSES_PATH", "/responses")
        self.LLM_IMAGE_GENERATIONS_PATH: str = os.getenv("LLM_IMAGE_GENERATIONS_PATH", "/images/generations")
        self.LLM_VOICE_TRANSCRIBE_PATH: str = os.getenv("LLM_VOICE_TRANSCRIBE_PATH", "/asr/transcribe")

        # ADK driver mode
        self.ADK_META_DRIVER: str = os.getenv("ADK_META_DRIVER", "custom_base_llm")

        # Timeouts & Operational Bounds (Constitution §5)
        self.SEARCH_TIMEOUT_SECONDS: float = float(os.getenv("SEARCH_TIMEOUT_SECONDS", "25.0"))
        self.IMAGE_TIMEOUT_SECONDS: float = float(os.getenv("IMAGE_TIMEOUT_SECONDS", "25.0"))
        self.STT_TIMEOUT_SECONDS: float = float(os.getenv("STT_TIMEOUT_SECONDS", "15.0"))
        self.SAM_TIMEOUT_SECONDS: float = float(os.getenv("SAM_TIMEOUT_SECONDS", "15.0"))
        self.LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30.0"))

        self.DAILY_BUILD_CAP: int = int(os.getenv("DAILY_BUILD_CAP", "6"))
        self.ARCHIVE_RETENTION_LIMIT: int = int(os.getenv("ARCHIVE_RETENTION_LIMIT", "60"))
        self.DEMO_INTERVAL_SECONDS: int = int(os.getenv("DEMO_INTERVAL_SECONDS", "120"))
        self.DEMO_CACHE_MODE: Literal["fallback", "always", "off"] = os.getenv(  # type: ignore[assignment]
            "DEMO_CACHE_MODE", "fallback"
        )

        # File system paths
        self.BASE_DIR: Path = BASE_DIR
        self.CONFIG_DIR: Path = BASE_DIR / "config"
        self.DESIGN_DIR: Path = BASE_DIR / "design"
        self.DATA_DIR: Path = BASE_DIR / "data"
        self.EDITIONS_DIR: Path = self.DATA_DIR / "editions"
        self.DEMO_CACHE_DIR: Path = self.DATA_DIR / "demo_cache"
        self.DB_PATH: Path = self.DATA_DIR / "your_daily_muse.db"

        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.DEMO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def chat_completions_url(self) -> str:
        return f"{self.LLM_API_BASE_URL}{self.LLM_CHAT_COMPLETIONS_PATH}"

    @property
    def responses_url(self) -> str:
        return f"{self.LLM_API_BASE_URL}{self.LLM_RESPONSES_PATH}"

    @property
    def image_generations_url(self) -> str:
        return f"{self.LLM_API_BASE_URL}{self.LLM_IMAGE_GENERATIONS_PATH}"

    @property
    def voice_transcribe_url(self) -> str:
        return f"{self.LLM_API_BASE_URL}{self.LLM_VOICE_TRANSCRIBE_PATH}"

    @property
    def has_live_api_key(self) -> bool:
        return bool(
            self.MODEL_API_KEY
            and self.MODEL_API_KEY != "your_meta_model_api_key_here"
            and self.LLM_API_BASE_URL
        )


settings = Settings()
