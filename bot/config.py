from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    genius_api_token: str | None
    download_dir: Path
    database_path: Path
    default_audio_quality: str
    max_file_size_bytes: int


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Configure it in .env")

    genius = os.getenv("GENIUS_API_TOKEN", "").strip() or None
    download_dir = Path(os.getenv("DOWNLOAD_DIR", "music")).expanduser()
    database_path = Path(os.getenv("DATABASE_PATH", "data/musicbot.db")).expanduser()
    quality = os.getenv("DEFAULT_AUDIO_QUALITY", "192").strip()
    max_mb = int(os.getenv("MAX_FILE_SIZE_MB", "49"))

    download_dir.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        telegram_bot_token=token,
        genius_api_token=genius,
        download_dir=download_dir,
        database_path=database_path,
        default_audio_quality=quality,
        max_file_size_bytes=max_mb * 1024 * 1024,
    )
