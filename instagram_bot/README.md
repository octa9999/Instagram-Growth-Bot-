# Instagram Reels Automation Bot

Modular bot for automated engagement with Instagram Reels (designers, founders, builders). Uses Playwright, OpenRouter for AI comments and niche classification, session cookies, configurable safety limits, and a live session report.

For a full professional overview (workflow + diagrams), see the repo root `README.md`.

## Setup

1. **Create virtual environment and install dependencies**

   ```bash
   cd instagram_bot
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configure environment**

   Copy `.env.example` to `.env` and set:

   - `OPENROUTER_API_KEY` — for AI comments and niche classification
   - `INSTAGRAM_USER` / `INSTAGRAM_PASS` — for login when cookies are missing

## Run

From the `instagram_bot` directory:

```bash
python main.py
```

You should see `Instagram Bot Started`. The browser will open; complete 2FA or challenge if prompted. The bot will then open Reels and run the engagement loop (niche detection, like/comment/follow with delays and hourly limits).

## Project structure

- `main.py` — entry point, source rotation, loop
- `config.py` — all config (keywords, hashtags, limits, delays)
- `bot/` — browser, session, reels navigation, actions, delays
- `ai/` — niche classifier, comment generator (OpenRouter)
- `utils/` — logger
