from __future__ import annotations

import json
import sqlite3
from collections import deque
from dataclasses import asdict
from pathlib import Path
from random import shuffle

from .models import QueueItem, Track


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT UNIQUE,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                webpage_url TEXT NOT NULL,
                filepath TEXT NOT NULL,
                duration INTEGER,
                uploader TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                filepath TEXT NOT NULL,
                source_url TEXT NOT NULL,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS queues (
                chat_id INTEGER PRIMARY KEY,
                items_json TEXT NOT NULL DEFAULT '[]',
                loop_enabled INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                items_json TEXT NOT NULL DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, name)
            );
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def upsert_track(self, track: Track) -> None:
        self.conn.execute(
            """
            INSERT INTO tracks (source_id, title, artist, webpage_url, filepath, duration, uploader)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                title=excluded.title,
                artist=excluded.artist,
                webpage_url=excluded.webpage_url,
                filepath=excluded.filepath,
                duration=excluded.duration,
                uploader=excluded.uploader
            """,
            (
                track.source_id,
                track.title,
                track.artist,
                track.webpage_url,
                track.filepath,
                track.duration,
                track.uploader,
            ),
        )
        self.conn.commit()

    def find_track_by_name(self, query: str) -> list[Track]:
        rows = self.conn.execute(
            """
            SELECT source_id, title, artist, webpage_url, filepath, duration, uploader
            FROM tracks
            WHERE title LIKE ? OR artist LIKE ?
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        return [
            Track(
                source_id=row["source_id"],
                title=row["title"],
                artist=row["artist"],
                webpage_url=row["webpage_url"],
                filepath=row["filepath"],
                duration=row["duration"],
                uploader=row["uploader"],
            )
            for row in rows
        ]

    def list_tracks(self, limit: int = 50) -> list[Track]:
        rows = self.conn.execute(
            """
            SELECT source_id, title, artist, webpage_url, filepath, duration, uploader
            FROM tracks
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            Track(
                source_id=row["source_id"],
                title=row["title"],
                artist=row["artist"],
                webpage_url=row["webpage_url"],
                filepath=row["filepath"],
                duration=row["duration"],
                uploader=row["uploader"],
            )
            for row in rows
        ]

    def get_track_by_source_id(self, source_id: str) -> Track | None:
        row = self.conn.execute(
            """
            SELECT source_id, title, artist, webpage_url, filepath, duration, uploader
            FROM tracks
            WHERE source_id = ?
            LIMIT 1
            """,
            (source_id,),
        ).fetchone()
        if row is None:
            return None

        return Track(
            source_id=row["source_id"],
            title=row["title"],
            artist=row["artist"],
            webpage_url=row["webpage_url"],
            filepath=row["filepath"],
            duration=row["duration"],
            uploader=row["uploader"],
        )

    def add_history(self, chat_id: int, item: QueueItem) -> None:
        self.conn.execute(
            """
            INSERT INTO history (chat_id, title, filepath, source_url)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, item.title, item.filepath, item.source_url),
        )
        self.conn.commit()

    def get_history(self, chat_id: int, limit: int = 20) -> list[QueueItem]:
        rows = self.conn.execute(
            """
            SELECT title, filepath, source_url
            FROM history
            WHERE chat_id = ?
            ORDER BY played_at DESC
            LIMIT ?
            """,
            (chat_id, limit),
        ).fetchall()
        return [
            QueueItem(title=row["title"], filepath=row["filepath"], source_url=row["source_url"])
            for row in rows
        ]

    def _read_queue_row(self, chat_id: int) -> tuple[deque[QueueItem], bool]:
        row = self.conn.execute(
            "SELECT items_json, loop_enabled FROM queues WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        if row is None:
            return deque(), False

        raw_items = json.loads(row["items_json"])
        queue = deque(QueueItem(**entry) for entry in raw_items)
        return queue, bool(row["loop_enabled"])

    def _write_queue_row(self, chat_id: int, queue: deque[QueueItem], loop_enabled: bool) -> None:
        payload = json.dumps([asdict(item) for item in queue], ensure_ascii=False)
        self.conn.execute(
            """
            INSERT INTO queues (chat_id, items_json, loop_enabled)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                items_json=excluded.items_json,
                loop_enabled=excluded.loop_enabled
            """,
            (chat_id, payload, int(loop_enabled)),
        )
        self.conn.commit()

    def queue_add(self, chat_id: int, item: QueueItem) -> int:
        queue, loop_enabled = self._read_queue_row(chat_id)
        queue.append(item)
        self._write_queue_row(chat_id, queue, loop_enabled)
        return len(queue)

    def queue_show(self, chat_id: int) -> tuple[list[QueueItem], bool]:
        queue, loop_enabled = self._read_queue_row(chat_id)
        return list(queue), loop_enabled

    def queue_pop(self, chat_id: int) -> QueueItem | None:
        queue, loop_enabled = self._read_queue_row(chat_id)
        if not queue:
            return None
        item = queue.popleft()
        if loop_enabled:
            queue.append(item)
        self._write_queue_row(chat_id, queue, loop_enabled)
        return item

    def queue_shuffle(self, chat_id: int) -> int:
        queue, loop_enabled = self._read_queue_row(chat_id)
        items = list(queue)
        shuffle(items)
        queue = deque(items)
        self._write_queue_row(chat_id, queue, loop_enabled)
        return len(queue)

    def queue_clear(self, chat_id: int) -> None:
        self._write_queue_row(chat_id, deque(), False)

    def queue_set_loop(self, chat_id: int, enabled: bool) -> None:
        queue, _ = self._read_queue_row(chat_id)
        self._write_queue_row(chat_id, queue, enabled)

    def playlist_save(self, chat_id: int, name: str, items: list[QueueItem]) -> None:
        payload = json.dumps([asdict(item) for item in items], ensure_ascii=False)
        self.conn.execute(
            """
            INSERT INTO playlists (chat_id, name, items_json)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id, name) DO UPDATE SET items_json=excluded.items_json
            """,
            (chat_id, name.strip().lower(), payload),
        )
        self.conn.commit()

    def playlist_load(self, chat_id: int, name: str) -> list[QueueItem]:
        row = self.conn.execute(
            "SELECT items_json FROM playlists WHERE chat_id = ? AND name = ?",
            (chat_id, name.strip().lower()),
        ).fetchone()
        if row is None:
            return []
        return [QueueItem(**entry) for entry in json.loads(row["items_json"])]

    def playlist_list(self, chat_id: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM playlists WHERE chat_id = ? ORDER BY created_at DESC",
            (chat_id,),
        ).fetchall()
        return [str(row["name"]) for row in rows]
