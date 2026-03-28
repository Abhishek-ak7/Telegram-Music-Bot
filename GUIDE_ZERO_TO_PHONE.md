# Zero → Phone Guide (Telegram Music Bot)

This guide starts from a fresh Linux machine and ends with controlling your bot from your phone.

## 1) What you need

- Linux PC/laptop with internet
- Telegram account on your phone
- Python 3.10+
- `ffmpeg`
- `pip`

Check versions:

```bash
python3 --version
pip3 --version
ffmpeg -version
```

If `ffmpeg` is missing:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

## 2) Create your Telegram bot token

On your **phone** (Telegram app):

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`.
3. Choose:
   - Bot display name (anything)
   - Bot username (must end with `bot`, e.g. `akMusicBot`)
4. BotFather sends your token like:
   - `1234567890:AA...`
5. Save this token (private).

Optional but useful:

- `/setdescription` and `/setuserpic` in BotFather
- `/setcommands` and paste:

```text
start - show help
play - play by link or song name
download - download to local library
local - play from local library
library - list saved songs
queue - queue add/show/clear
skip - play next queued song
shuffle - shuffle queue
loop - toggle queue loop
playlist - save/load/list playlists
history - show recently played
lyrics - show top Genius match
trending - show trending tracks
```

## 3) Prepare project locally

From your project folder:

```bash
cd /home/ak/projects/music-player
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4) Configure `.env`

```bash
cp .env.example .env
nano .env
```

Set at minimum:

```env
TELEGRAM_BOT_TOKEN=PASTE_YOUR_TOKEN_HERE
DOWNLOAD_DIR=music
DATABASE_PATH=data/musicbot.db
DEFAULT_AUDIO_QUALITY=192
MAX_FILE_SIZE_MB=49
```

Optional:

```env
GENIUS_API_TOKEN=...
```

## 5) Start the bot

```bash
cd /home/ak/projects/music-player
source .venv/bin/activate
python -m bot.main
```

If startup is OK, it stays running and waits for messages.

## 6) Access from your phone

1. In Telegram app, search your bot username.
2. Open chat and tap **Start** (or send `/start`).
3. Test commands:

```text
/play faded alan walker
/play https://www.youtube.com/watch?v=dQw4w9WgXcQ
/download believer imagine dragons
/library
/local believer
/queue add blinding lights
/queue show
/skip
/shuffle
/loop
/playlist save gym
/playlist list
/playlist load gym
/history
/trending
```

You should receive audio files in the chat.

You can also just send a plain message with a song name (example: `kesariya arijit singh`).
The bot will download it from internet and save it in library for later offline use with `/local`.
If the song is already in your local library, it skips re-download and uses the saved copy.

### Use music from phone local storage

Telegram bots cannot directly browse your phone filesystem, but you can share files from storage to the bot:

1. In your bot chat, tap attachment icon.
2. Choose **File** (or **Music**) and pick a song from your phone storage (`.mp3`, `.m4a`, etc.).
3. Send it to the bot.
4. Bot saves it in local library automatically.
5. Play later offline with:

```text
/library
/local <part-of-song-name>
```

## 7) Keep it running (important)

Your phone can use the bot only while the bot process is alive.

Quick way (single terminal):

```bash
source .venv/bin/activate
python -m bot.main
```

Better way with `tmux`:

```bash
sudo apt install -y tmux
tmux new -s musicbot
cd /home/ak/projects/music-player
source .venv/bin/activate
python -m bot.main
```

Detach from tmux: `Ctrl+B`, then `D`.
Re-attach later:

```bash
tmux attach -t musicbot
```

## 8) Common issues

### Bot does not reply on phone

- Make sure process is running on PC
- Confirm token in `.env` is correct
- Confirm you started chat with the bot and pressed **Start**

### `ffmpeg` errors

Install and verify:

```bash
sudo apt install -y ffmpeg
ffmpeg -version
```

### Download fails for some links

`yt-dlp` can break when sites change. Update it:

```bash
source .venv/bin/activate
pip install -U yt-dlp
```

### File too large

Lower quality in `.env`:

```env
DEFAULT_AUDIO_QUALITY=128
MAX_FILE_SIZE_MB=49
```

Restart bot after changes.

## 9) Optional: run 24/7 in cloud

If you want always-on access from phone, deploy this bot to a VPS or free tier host (Railway/Render/Oracle Free Tier). Polling mode works fine if process stays alive.

## 10) Daily usage flow (simple)

1. Send `/play <song>` for instant playback in chat
2. Send `/download <song>` to store locally
3. Use `/queue add ...` to build session queue
4. Save queues with `/playlist save <name>`
5. Use `/history` to quickly replay recent tracks

Done — if terminal is running and your phone has Telegram, you can control the bot from anywhere.
