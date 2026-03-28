# 🎵 Telegram Music Bot

A simple Telegram bot that lets you search, download, and play music with a local offline library.

## Why this bot?

- Play songs from a URL or search text with `/play`.
- Save songs permanently with `/download`.
- Auto-save when you send plain text (song name).
- Upload audio files from your phone directly to the library.
- Manage queue, playlists, and history.
- Optional extras: lyrics (`/lyrics`) and trending tracks (`/trending`).

## Quick Start

For a full phone-first walkthrough, see [GUIDE_ZERO_TO_PHONE.md](GUIDE_ZERO_TO_PHONE.md).

### 1) Create your Telegram bot

1. Open Telegram and start **@BotFather**.
2. Run `/newbot` and follow the prompts.
3. Copy your bot token.

### 2) Install prerequisites

- Python 3.9+
- `ffmpeg` available in your `PATH`

### 3) Install dependencies

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

### 4) Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```dotenv
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 5) Run the bot

```bash
. .venv/bin/activate
python -m bot.main
```

## Commands

### Core

- `/start` — Show quick intro and available commands.
- `/play <song or URL>` — Download best audio and send to chat.
- `/download <song or URL>` — Save to local library.
- `/local <song name>` — Play from local storage.
- `/library` — Show local tracks with tap-to-play inline buttons.

### Queue

- `/queue add <song or URL>` — Add a track to queue.
- `/queue show` — View queue.
- `/queue clear` — Clear queue.
- `/skip` — Play next item from queue.
- `/shuffle` — Shuffle current queue.
- `/loop` — Toggle queue loop.

### Playlists

- `/playlist save <name>` — Save current queue as playlist.
- `/playlist load <name>` — Load playlist into queue.
- `/playlist list` — List saved playlists.

### Extras

- `/history` — Show recent played tracks.
- `/lyrics <song>` — Get lyrics (uses Genius API token if provided).
- `/trending` — Show trending track names.

## Auto Behaviors

- Sending plain text (for example, `Shape of You`) auto-searches and saves the song.
- Sending an audio/document file (`.mp3`, `.m4a`, `.wav`, etc.) stores it in your local library.
- If a requested track is already saved locally, the bot reuses the local copy.

## Environment Variables

From `.env.example`:

- `TELEGRAM_BOT_TOKEN` (required)
- `GENIUS_API_TOKEN` (optional, for lyrics)
- `DOWNLOAD_DIR` (default: `music`)
- `DATABASE_PATH` (default: `data/musicbot.db`)
- `DEFAULT_AUDIO_QUALITY` (default: `192`)
- `MAX_FILE_SIZE_MB` (default: `49`)

## Project Structure

```text
bot/        # Telegram bot source code
data/       # SQLite database (runtime)
music/      # Downloaded audio files (runtime)
```

## Troubleshooting

- **`TELEGRAM_BOT_TOKEN is not set`**
   - Make sure `.env` exists and contains `TELEGRAM_BOT_TOKEN=...`.
- **Download/search fails**
   - Check internet connectivity and confirm source URLs are valid.
- **Audio conversion issues**
   - Verify `ffmpeg` is installed and available in your terminal.
- **Large file blocked**
   - Telegram file limits apply; tune `MAX_FILE_SIZE_MB` if needed.

## Notes

- This bot uses polling mode (run from the virtualenv with `python -m bot.main`).
- Downloaded files and DB are local to your machine.
- Keep your bot token private and never commit `.env`.
