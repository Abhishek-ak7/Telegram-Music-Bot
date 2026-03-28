from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Track:
    source_id: str
    title: str
    artist: str
    webpage_url: str
    filepath: str
    duration: int | None
    uploader: str | None


@dataclass(slots=True)
class QueueItem:
    title: str
    filepath: str
    source_url: str
