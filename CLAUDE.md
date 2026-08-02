# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

`whatsapp-demo-chatbot-python` — a demo WhatsApp chatbot built on the
[GREEN-API](https://green-api.com) service. The bot logic lives in `bot.py`,
with helpers under `internal/` and message content in `config/data.yml`.

---

## WhatsApp connection via Green API (READ THIS FIRST)

This repository is connected to WhatsApp through **Green API**. Whenever you
need to send a WhatsApp message, send a file, or read incoming messages, you
act through the Green API HTTP endpoints using the credentials stored in the
**`.env` file in the repository root**.

### Always read the credentials from `.env`

The `.env` file holds exactly these four fields, named exactly as they appear
in the Green API panel (https://console.green-api.com):

| Field              | Meaning                                             | Example                        |
| ------------------ | --------------------------------------------------- | ------------------------------ |
| `idInstance`       | The instance id                                     | `1101000001`                   |
| `apiTokenInstance` | The instance API token (secret)                     | `a1b2c3...` (long string)      |
| `apiUrl`           | Host for text/JSON requests                         | `https://api.green-api.com`    |
| `mediaUrl`         | Host for sending files                              | `https://media.green-api.com`  |

**Rules — never break these:**

1. **Always** read the current values from `.env` at the moment you need them.
   Never hard-code, guess, cache across sessions, or invent these values.
2. If `.env` is missing or any of the four fields is empty, **stop and ask the
   user to fill it in** (by copy-pasting from the Green API panel). Do not
   proceed with placeholder values.
3. **Never print, echo, log, or commit** the value of `apiTokenInstance` (or the
   full request URL, which contains it). `.env` is git-ignored — keep it that
   way. Treat the token as a secret.

A convenient way to load them in a shell:

```bash
set -a && . ./.env && set +a
```

Or in Python (the project already depends on `python-dotenv`):

```python
import os
from dotenv import load_dotenv
load_dotenv()  # loads .env from the repo root
id_instance   = os.environ["idInstance"]
api_token     = os.environ["apiTokenInstance"]
api_url       = os.environ["apiUrl"].rstrip("/")
media_url     = os.environ["mediaUrl"].rstrip("/")
```

### How Green API URLs are built

Every Green API request follows this shape:

```
{host}/waInstance{idInstance}/{method}/{apiTokenInstance}
```

- Use **`apiUrl`** as `{host}` for text and JSON methods (`sendMessage`,
  `receiveNotification`, `getStateInstance`, ...).
- Use **`mediaUrl`** as `{host}` for file methods (`sendFileByUrl`,
  `sendFileByUpload`, ...).

`chatId` format: `<phone-with-country-code>@c.us` for a person
(e.g. `972501234567@c.us`), or `<group-id>@g.us` for a group.

### Common operations (copy-paste patterns)

**Check the instance is authorized (should return `{"stateInstance":"authorized"}`):**

```bash
set -a && . ./.env && set +a
curl -s "${apiUrl}/waInstance${idInstance}/getStateInstance/${apiTokenInstance}"
```

**Send a text message:**

```bash
set -a && . ./.env && set +a
curl -s -X POST \
  "${apiUrl}/waInstance${idInstance}/sendMessage/${apiTokenInstance}" \
  -H "Content-Type: application/json" \
  -d '{"chatId":"972501234567@c.us","message":"Hello from Claude 👋"}'
```

**Send a file by URL:**

```bash
set -a && . ./.env && set +a
curl -s -X POST \
  "${mediaUrl}/waInstance${idInstance}/sendFileByUrl/${apiTokenInstance}" \
  -H "Content-Type: application/json" \
  -d '{"chatId":"972501234567@c.us","urlFile":"https://example.com/file.pdf","fileName":"file.pdf","caption":"Here you go"}'
```

**Read the next incoming message (poll), then delete it from the queue:**

```bash
set -a && . ./.env && set +a
# Receive one notification (returns null when the queue is empty):
curl -s "${apiUrl}/waInstance${idInstance}/receiveNotification/${apiTokenInstance}"
# Delete it after processing, using the receiptId from the response:
curl -s -X DELETE "${apiUrl}/waInstance${idInstance}/deleteNotification/${apiTokenInstance}/<receiptId>"
```

Full method reference: https://green-api.com/en/docs/api/

---

## Repository notes

- Runtime settings for the demo bot are loaded in `internal/envs.py` from
  `config/.env` (a separate concern from the root `.env` above, which is what
  *Claude* uses to talk to WhatsApp).
- Install dependencies with `python -m pip install -r requirements.txt`.
- Keep all secrets out of git; both `.env` and `config/.env` are git-ignored.
