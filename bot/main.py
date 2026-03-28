from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import load_settings
from .db import Database
from .downloader import Downloader
from .handlers import (
    auto_download_text,
    download,
    history,
    inline_controls,
    library,
    local,
    loop,
    lyrics,
    play,
    playlist,
    queue_cmd,
    save_phone_audio,
    shuffle_cmd,
    skip,
    start,
    trending,
)


def _configure_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    _configure_logging()
    settings = load_settings()

    db = Database(settings.database_path)
    downloader = Downloader(
        download_dir=settings.download_dir,
        audio_quality=settings.default_audio_quality,
        max_file_size_bytes=settings.max_file_size_bytes,
    )

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .connect_timeout(30)
        .read_timeout(180)
        .write_timeout(180)
        .pool_timeout(30)
        .build()
    )
    app.bot_data["settings"] = settings
    app.bot_data["db"] = db
    app.bot_data["downloader"] = downloader

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("download", download))
    app.add_handler(CommandHandler("local", local))
    app.add_handler(CommandHandler("library", library))
    app.add_handler(CommandHandler("queue", queue_cmd))
    app.add_handler(CommandHandler("skip", skip))
    app.add_handler(CommandHandler("shuffle", shuffle_cmd))
    app.add_handler(CommandHandler("loop", loop))
    app.add_handler(CommandHandler("playlist", playlist))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("lyrics", lyrics))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CallbackQueryHandler(inline_controls))
    app.add_handler(MessageHandler(filters.AUDIO | filters.Document.ALL, save_phone_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_download_text))

    try:
        app.run_polling(close_loop=False)
    finally:
        db.close()


if __name__ == "__main__":
    main()
