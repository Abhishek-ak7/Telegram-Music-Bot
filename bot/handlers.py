from __future__ import annotations

import re
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .db import Database
from .downloader import Downloader
from .models import QueueItem, Track
from .services import fetch_lyrics


SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".wma"}


def _controls() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⏮", callback_data="prev"),
                InlineKeyboardButton("⏯", callback_data="toggle"),
                InlineKeyboardButton("⏭", callback_data="skip"),
                InlineKeyboardButton("🔀", callback_data="shuffle"),
                InlineKeyboardButton("🔁", callback_data="loop"),
            ]
        ]
    )


def _library_controls(tracks: list[Track]) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for idx, track in enumerate(tracks, start=1):
        label = f"▶️ {idx}. {track.title[:28]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"libplay:{track.source_id}")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Music bot ready.\n"
        "Use /play <song or URL> to start.\n"
        "Commands: /download /local /library /queue /playlist /history /lyrics /trending\n"
        "You can also send an audio file from your phone to save it offline."
    )


def _safe_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("._") or "audio.mp3"


def _is_supported_audio_document_maybe(document_mime_type: str | None, file_name: str | None) -> bool:
    if document_mime_type and document_mime_type.startswith("audio/"):
        return True
    if not file_name:
        return False
    return Path(file_name).suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS


def _find_existing_local_track(db: Database, query: str) -> Track | None:
    matches = db.find_track_by_name(query)
    for track in matches:
        if Path(track.filepath).exists():
            return track
    return None


async def save_phone_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    db: Database = context.application.bot_data["db"]
    settings = context.application.bot_data["settings"]

    audio = update.message.audio
    document = update.message.document

    if audio:
        file_id = audio.file_id
        unique_id = audio.file_unique_id
        title = audio.title or audio.file_name or f"upload_{unique_id}"
        performer = audio.performer or "Unknown Artist"
        duration = audio.duration
        original_name = audio.file_name or f"{unique_id}.mp3"
    elif document and _is_supported_audio_document_maybe(document.mime_type, document.file_name):
        file_id = document.file_id
        unique_id = document.file_unique_id
        title = Path(document.file_name).stem if document.file_name else f"upload_{unique_id}"
        performer = "Unknown Artist"
        duration = None
        original_name = document.file_name or f"{unique_id}.mp3"
    else:
        return

    status = await update.message.reply_text("Saving uploaded audio to local library…")
    extension = Path(original_name).suffix or ".mp3"
    filename = _safe_filename(f"tg-{unique_id}-{title}{extension}")
    target_path = settings.download_dir / filename

    try:
        telegram_file = await context.bot.get_file(file_id)
        await telegram_file.download_to_drive(custom_path=str(target_path))

        track = Track(
            source_id=f"tg_{unique_id}",
            title=title,
            artist=performer,
            webpage_url=f"telegram://file/{file_id}",
            filepath=str(target_path),
            duration=duration,
            uploader="telegram_upload",
        )
        item = QueueItem(title=track.title, filepath=track.filepath, source_url=track.webpage_url)
        db.upsert_track(track)
        db.add_history(update.effective_chat.id, item)

        await status.edit_text(
            f"Saved to library: {track.title} — {track.artist}\nUse /local {track.title} to play offline."
        )
    except Exception as exc:
        await status.edit_text(f"Failed to save upload: {exc}")


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Usage: /play <song name or URL>")
        return

    db: Database = context.application.bot_data["db"]
    downloader: Downloader = context.application.bot_data["downloader"]

    is_url = query.startswith("http://") or query.startswith("https://")
    if not is_url:
        existing = _find_existing_local_track(db, query)
        if existing:
            path = Path(existing.filepath)
            item = QueueItem(title=existing.title, filepath=str(path), source_url=existing.webpage_url)
            db.add_history(update.effective_chat.id, item)
            with path.open("rb") as music:
                await update.message.reply_audio(
                    audio=music,
                    caption=f"From library: {existing.title} — {existing.artist}",
                    title=existing.title,
                    performer=existing.artist,
                    reply_markup=_controls(),
                )
            return

    progress = await update.message.reply_text("Searching…")
    try:
        await progress.edit_text("Downloading…")
        track, item = await downloader.fetch_mp3(query, save_permanently=True)
        db.upsert_track(track)
        db.add_history(update.effective_chat.id, item)
        await progress.edit_text("Sending… 🎵")
        with Path(item.filepath).open("rb") as music:
            await update.message.reply_audio(
                audio=music,
                caption=f"{track.title} — {track.artist}",
                title=track.title,
                performer=track.artist,
                reply_markup=_controls(),
            )
        await progress.delete()
    except Exception as exc:
        await progress.edit_text(f"Failed: {exc}")


async def download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Usage: /download <song name or URL>")
        return

    db: Database = context.application.bot_data["db"]
    downloader: Downloader = context.application.bot_data["downloader"]

    msg = await update.message.reply_text("Downloading for local library…")
    try:
        track, item = await downloader.fetch_mp3(query, save_permanently=True)
        db.upsert_track(track)
        db.add_history(update.effective_chat.id, item)
        await msg.edit_text(f"Saved: {track.title} — {track.artist}")
    except Exception as exc:
        await msg.edit_text(f"Download failed: {exc}")


async def auto_download_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    query = update.message.text.strip()
    if not query or query.startswith("/"):
        return

    db: Database = context.application.bot_data["db"]
    downloader: Downloader = context.application.bot_data["downloader"]

    existing = _find_existing_local_track(db, query)
    if existing:
        item = QueueItem(title=existing.title, filepath=existing.filepath, source_url=existing.webpage_url)
        db.add_history(update.effective_chat.id, item)
        await update.message.reply_text(
            f"Already in library: {existing.title} — {existing.artist}\n"
            f"Play offline with: /local {existing.title}"
        )
        return

    msg = await update.message.reply_text("Searching and downloading to library…")
    try:
        track, item = await downloader.fetch_mp3(query, save_permanently=True)
        db.upsert_track(track)
        db.add_history(update.effective_chat.id, item)
        await msg.edit_text(
            f"Saved in library: {track.title} — {track.artist}\n"
            f"Play later with: /local {track.title}"
        )
    except Exception as exc:
        await msg.edit_text(f"Auto-download failed: {exc}")


async def local(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Usage: /local <song name>")
        return

    db: Database = context.application.bot_data["db"]
    matches = db.find_track_by_name(query)
    if not matches:
        await update.message.reply_text("No local match found. Use /download first.")
        return

    track = matches[0]
    path = Path(track.filepath)
    if not path.exists():
        await update.message.reply_text("Track metadata exists but file is missing on disk.")
        return

    item = QueueItem(title=track.title, filepath=str(path), source_url=track.webpage_url)
    db.add_history(update.effective_chat.id, item)

    with path.open("rb") as music:
        await update.message.reply_audio(
            audio=music,
            caption=f"Local: {track.title} — {track.artist}",
            title=track.title,
            performer=track.artist,
            reply_markup=_controls(),
        )


async def library(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    db: Database = context.application.bot_data["db"]
    tracks = db.list_tracks(limit=30)
    if not tracks:
        await update.message.reply_text("Library is empty.")
        return

    lines = [f"{i+1}. {t.title} — {t.artist}" for i, t in enumerate(tracks)]
    await update.message.reply_text(
        "Local library:\n" + "\n".join(lines),
        reply_markup=_library_controls(tracks),
    )


async def queue_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    db: Database = context.application.bot_data["db"]
    downloader: Downloader = context.application.bot_data["downloader"]
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("Usage: /queue <add|show|clear> [query]")
        return

    sub = context.args[0].lower()
    rest = " ".join(context.args[1:]).strip()

    if sub == "add":
        if not rest:
            await update.message.reply_text("Usage: /queue add <song or URL>")
            return
        status = await update.message.reply_text("Fetching for queue…")
        try:
            track, item = await downloader.fetch_mp3(rest, save_permanently=True)
            db.upsert_track(track)
            size = db.queue_add(chat_id, item)
            await status.edit_text(f"Added to queue ({size}): {item.title}")
        except Exception as exc:
            await status.edit_text(f"Queue add failed: {exc}")
        return

    if sub == "show":
        items, loop_enabled = db.queue_show(chat_id)
        if not items:
            await update.message.reply_text("Queue is empty.")
            return
        prefix = "🔁 loop on\n" if loop_enabled else ""
        text = prefix + "\n".join(f"{i+1}. {x.title}" for i, x in enumerate(items[:25]))
        await update.message.reply_text(text)
        return

    if sub == "clear":
        db.queue_clear(chat_id)
        await update.message.reply_text("Queue cleared.")
        return

    await update.message.reply_text("Unknown queue action. Use add/show/clear.")


async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id

    item = db.queue_pop(chat_id)
    if not item:
        await update.message.reply_text("Queue is empty.")
        return

    path = Path(item.filepath)
    if not path.exists():
        await update.message.reply_text("Next queued file is missing.")
        return

    db.add_history(chat_id, item)
    with path.open("rb") as music:
        await update.message.reply_audio(
            audio=music,
            caption=f"Now playing: {item.title}",
            title=item.title,
            reply_markup=_controls(),
        )


async def shuffle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    db: Database = context.application.bot_data["db"]
    size = db.queue_shuffle(update.effective_chat.id)
    await update.message.reply_text(f"Shuffled queue ({size} item(s)).")


async def loop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id

    current_items, is_on = db.queue_show(chat_id)
    db.queue_set_loop(chat_id, not is_on)
    _ = current_items
    await update.message.reply_text(f"Loop {'enabled' if not is_on else 'disabled'}.")


async def playlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id

    if len(context.args) < 1:
        await update.message.reply_text("Usage: /playlist <save|load|list> [name]")
        return

    sub = context.args[0].lower()

    if sub == "list":
        names = db.playlist_list(chat_id)
        if not names:
            await update.message.reply_text("No playlists yet.")
            return
        await update.message.reply_text("Playlists:\n" + "\n".join(names))
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /playlist save|load <name>")
        return

    name = " ".join(context.args[1:]).strip()
    if sub == "save":
        items, _ = db.queue_show(chat_id)
        if not items:
            await update.message.reply_text("Queue is empty. Add songs before saving.")
            return
        db.playlist_save(chat_id, name, items)
        await update.message.reply_text(f"Playlist saved: {name}")
        return

    if sub == "load":
        items = db.playlist_load(chat_id, name)
        if not items:
            await update.message.reply_text("Playlist not found or empty.")
            return
        db.queue_clear(chat_id)
        for item in items:
            db.queue_add(chat_id, item)
        await update.message.reply_text(f"Loaded playlist '{name}' with {len(items)} item(s).")
        return

    await update.message.reply_text("Unknown playlist action. Use save/load/list.")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    db: Database = context.application.bot_data["db"]
    items = db.get_history(update.effective_chat.id, limit=20)
    if not items:
        await update.message.reply_text("No history yet.")
        return

    await update.message.reply_text("Recent history:\n" + "\n".join(f"- {i.title}" for i in items))


async def lyrics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    song = " ".join(context.args).strip()
    if not song:
        await update.message.reply_text("Usage: /lyrics <song>")
        return

    settings = context.application.bot_data["settings"]
    text = await fetch_lyrics(song, settings.genius_api_token)
    await update.message.reply_text(text)


async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    downloader: Downloader = context.application.bot_data["downloader"]
    results = await downloader.trending(limit=10)
    if not results:
        await update.message.reply_text("No trending results available.")
        return
    await update.message.reply_text("Trending now:\n" + "\n".join(f"{i+1}. {name}" for i, name in enumerate(results)))


async def inline_controls(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    db: Database = context.application.bot_data["db"]
    chat_id = query.message.chat.id if query.message else update.effective_chat.id

    data = query.data
    if data == "skip":
        item = db.queue_pop(chat_id)
        if not item:
            await query.answer("Queue empty")
        else:
            await query.answer(f"Skipped to: {item.title}")
    elif data == "shuffle":
        db.queue_shuffle(chat_id)
        await query.answer("Queue shuffled")
    elif data == "loop":
        _, is_on = db.queue_show(chat_id)
        db.queue_set_loop(chat_id, not is_on)
        await query.answer(f"Loop {'on' if not is_on else 'off'}")
    elif data and data.startswith("libplay:"):
        source_id = data.split(":", 1)[1]
        track = db.get_track_by_source_id(source_id)
        if track is None:
            await query.answer("Track not found")
            return

        path = Path(track.filepath)
        if not path.exists():
            await query.answer("File missing on disk")
            return

        item = QueueItem(title=track.title, filepath=str(path), source_url=track.webpage_url)
        db.add_history(chat_id, item)

        await query.answer("Playing from library")
        if query.message:
            with path.open("rb") as music:
                await query.message.reply_audio(
                    audio=music,
                    caption=f"Local: {track.title} — {track.artist}",
                    title=track.title,
                    performer=track.artist,
                    reply_markup=_controls(),
                )
    else:
        await query.answer("Not implemented")
