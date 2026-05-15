# Requirements layout

This layout splits dependencies by responsibility:

- `base.txt` — shared app dependencies
- `bot.txt` — Telegram bot / MTProto
- `api.txt` — FastAPI app
- `parsing.txt` — scraping / HTML parsing / feed parsing
- `ai.txt` — LLM / AI providers
- `ocr.txt` — OCR / image analysis extras
- `dev.txt` — local development, tests, linters
- `prod.txt` — convenience file for a "full local/prod-like" install
- `requirements.txt` — alias to `prod.txt`

Recommended install flows:

```bash
pip install -r requirements/base.txt -r requirements/bot.txt -r requirements/api.txt
```

or full setup:

```bash
pip install -r requirements/requirements.txt
```
