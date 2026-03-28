from __future__ import annotations

import asyncio
from pathlib import Path

import yt_dlp
from mutagen.mp3 import MP3

from .models import QueueItem, Track


class Downloader:
    def __init__(self, download_dir: Path, audio_quality: str, max_file_size_bytes: int):
        self.download_dir = download_dir
        self.audio_quality = audio_quality
        self.max_file_size_bytes = max_file_size_bytes

    async def fetch_mp3(self, query: str, save_permanently: bool = True) -> tuple[Track, QueueItem]:
        return await asyncio.to_thread(self._fetch_sync, query, save_permanently)

    def _candidate_targets(self, query: str) -> list[str]:
        normalized = " ".join(query.split())
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return [normalized]

        return [
            f"ytsearch1:{normalized}",
            f"ytsearch3:{normalized} official audio",
            f"ytsearch3:{normalized} topic",
            f"scsearch3:{normalized}",
            f"ytsearch5:{normalized}",
        ]

    def _fetch_sync(self, query: str, save_permanently: bool) -> tuple[Track, QueueItem]:
        outtmpl = str(self.download_dir / "%(id)s-%(title).80s.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "extract_flat": False,
            "outtmpl": outtmpl,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": self.audio_quality,
                }
            ],
        }

        attempts: list[str] = []
        for target in self._candidate_targets(query):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(target, download=True)
                    if "entries" in info:
                        entries = info.get("entries") or []
                        if not entries:
                            raise RuntimeError("No entries found")
                        info = entries[0]

                    source_id = str(info.get("id") or "unknown")
                    title = str(info.get("title") or "Unknown Title")
                    artist = str(info.get("artist") or info.get("channel") or "Unknown Artist")
                    webpage_url = str(info.get("webpage_url") or info.get("original_url") or "")
                    uploader = info.get("uploader")

                    guessed = ydl.prepare_filename(info)
                    audio_path = Path(guessed).with_suffix(".mp3")
                    if not audio_path.exists():
                        candidates = sorted(self.download_dir.glob(f"{source_id}-*.mp3"), reverse=True)
                        if not candidates:
                            raise RuntimeError("Could not locate converted MP3 file after download")
                        audio_path = candidates[0]

                    if audio_path.stat().st_size > self.max_file_size_bytes:
                        raise RuntimeError(
                            f"Audio file exceeds size limit ({audio_path.stat().st_size // (1024 * 1024)}MB). "
                            "Try a shorter track or lower quality."
                        )

                    duration = None
                    try:
                        duration = int(MP3(audio_path).info.length)
                    except Exception:
                        duration = info.get("duration")

                    if not save_permanently:
                        temp_path = self.download_dir / f"temp-{audio_path.name}"
                        audio_path.rename(temp_path)
                        audio_path = temp_path

                    track = Track(
                        source_id=source_id,
                        title=title,
                        artist=artist,
                        webpage_url=webpage_url,
                        filepath=str(audio_path),
                        duration=duration,
                        uploader=str(uploader) if uploader else None,
                    )
                    queue_item = QueueItem(title=title, filepath=str(audio_path), source_url=webpage_url)
                    return track, queue_item
            except Exception as exc:
                attempts.append(f"{target} -> {exc}")

        raise RuntimeError(
            "Could not find/download song from primary or fallback sources. "
            + " | ".join(attempts[-3:])
        )

    async def trending(self, limit: int = 10) -> list[str]:
        return await asyncio.to_thread(self._trending_sync, limit)

    def _trending_sync(self, limit: int) -> list[str]:
        target = f"ytsearch{max(5, limit)}:youtube music trending songs"
        opts = {
            "quiet": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target, download=False)
            entries = info.get("entries", [])
            names: list[str] = []
            for entry in entries[:limit]:
                title = str(entry.get("title") or "Unknown")
                channel = str(entry.get("uploader") or entry.get("channel") or "Unknown")
                names.append(f"{title} — {channel}")
            return names
