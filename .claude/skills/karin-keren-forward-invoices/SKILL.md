---
name: karin-keren-forward-invoices
description: >
  Karin's workflow for handling invoices that arrive in her email and forwarding them to
  Maayan and to the accountant (רו"ח) via WhatsApp. Use this skill whenever Karin asks to
  handle, forward, send, or "push out" invoices/receipts that came by email — including
  phrasings like "תעבירי את החשבוניות", "שלחי את החשבונית למעיין ולרו״ח", "יש חשבונית חדשה
  במייל", "forward the invoice", "send this invoice to the accountant", or whenever a new
  invoice email is detected and the natural next step is to forward it. Trigger even if
  Karin does not say the exact word "invoice" — if an email carries a supplier bill/receipt
  that needs to reach Maayan and the accountant, this skill applies. Do NOT use it for
  documents that need a client signature (use karin-keren-send-for-signature) or for
  purely informational emails.
---

# Forward Email Invoices to Maayan & the Accountant (WhatsApp)

This skill turns "תעבירי את החשבוניות" into a complete, repeatable action: find the invoice
emails in Gmail, pull out each invoice's key details, and forward the file + a short Hebrew
summary to Maayan and to the accountant on WhatsApp — without sending duplicates and without
sending anything Karin didn't intend. The goal is that Karin can say two words and trust that
every invoice reaches both people, once.

## Configuration — fill these once

The only things this skill cannot guess are the two WhatsApp numbers. Fill them here on first
use (international format, digits only, no `+`, e.g. `972501234567`):

```
MAAYAN_WHATSAPP    = 972532248724   # מעיין, מנהלת משרד (053-2248724)
ACCOUNTANT_NAME    = ספואן נג׳אר, רו״ח
ACCOUNTANT_WHATSAPP= 972559734494   # ספואן נג׳אר, רו״ח (055-9734494)

# behaviour switches (defaults chosen for safety)
CONFIRM_BEFORE_SEND = true      # true = show a preview and wait for "שלח"; false = auto-send
INVOICE_LABEL       = חשבוניות  # Gmail label that also marks an email as an invoice
PROCESSED_LABEL     = נשלח לרו״ח # applied after a successful forward, prevents re-sending
```

If a number is still blank, try to resolve it before asking Karin:
1. **Base44 CRM** (app `69ed0157e2731f27bece9d50`) — a contact named "מעיין" / the accountant.
2. If it still can't be found, ask Karin for that one number and offer to save it here.

Never invent or guess a phone number.

## Prerequisites (verify, don't assume)

- **Gmail** connector — to read the invoice emails and their attachments.
- **WhatsApp** via Green API (instance **7107653407**) — the sending hand. The repo's client
  (`whatsapp-api-client-python`) sends files with:
  - `api.sending.sendFileByUrl(chatId, urlFile, fileName, caption=...)` — when the file has a
    public URL.
  - `api.sending.sendFileByUpload(chatId, path, fileName, caption=...)` — when forwarding a
    local attachment saved from the email (the usual case here).
  - `chatId` is `"<number>@c.us"`, e.g. `972501234567@c.us`.

**The actual send runs through `tools/forward_invoice_whatsapp.py`** (in this repo). A chat
session can *find* invoices but cannot download attachment bytes or hold the Green API token,
so the send is delegated to that script, which does both. Run it where the credentials live:

```bash
# forward straight from a Gmail message:
python tools/forward_invoice_whatsapp.py --gmail-message-id <ID> --to accountant --to maayan \
    --caption "חשבונית להעברה"
# or send a PDF already on disk:
python tools/forward_invoice_whatsapp.py --file receipt.pdf --to accountant
```

It reads `GREENAPI_ID_INSTANCE` / `GREENAPI_API_TOKEN` (and Google OAuth for Gmail mode) from
the environment — never paste those secrets into chat.

If Gmail or the WhatsApp channel isn't connected — or the Green API token isn't set in the
environment — do **not** claim anything was forwarded. Tell Karin exactly what to set (env vars
above), and meanwhile produce a ready-to-send summary + the exact command she can run.

## Step 1 — Find the invoice emails

Search Gmail for candidate emails that are **not yet processed**. An email is an invoice when:

- it carries a **PDF or image attachment**, **and** the subject/body contains an invoice
  keyword — `חשבונית`, `חשבונית מס`, `קבלה`, `חשבונית/קבלה`, `invoice`, `receipt`, `tax invoice`;
  **or**
- it sits under the Gmail label **`INVOICE_LABEL`** ("חשבוניות").

Exclude anything already carrying **`PROCESSED_LABEL`** ("נשלח לרו״ח").

Default scope: newest unprocessed first. If Karin named a timeframe ("של החודש", "מהשבוע"),
scope the search to it. If she pointed at one specific email/attachment already in the
conversation, skip the search and use that.

## Step 2 — Extract each invoice's key details

For every candidate, read the attachment and pull:

- **ספק** (supplier / sender name)
- **סכום** (total, incl. VAT — with currency)
- **תאריך** (invoice date)
- **מספר חשבונית** (invoice / receipt number)

If a field is genuinely unreadable, leave it out of the summary rather than guessing. Keep the
original file — forward it as-is; do not re-render or alter it.

## Step 3 — Preview and confirm (default)

When `CONFIRM_BEFORE_SEND = true`, show Karin a compact list before sending anything:

```
מצאתי N חשבוניות להעברה למעיין ולרו״ח:
1. [ספק] · [סכום] · [תאריך] · מס׳ [מספר]   (קובץ: invoice.pdf)
2. ...
לשלוח? (כתבי "שלח" / "שלח רק 1,3" / "בטל")
```

Send only after she confirms. If `CONFIRM_BEFORE_SEND = false`, skip this step and send
directly (use only when Karin has explicitly asked for automatic forwarding).

## Step 4 — Forward to both recipients on WhatsApp

For each approved invoice, send the **attachment + a short Hebrew (RTL) caption** to **both**
`MAAYAN_WHATSAPP` and `ACCOUNTANT_WHATSAPP`.

**Caption template** (drop any line whose value is unknown):

```
חשבונית להעברה 📄
ספק: [ספק]
סכום: [סכום]
תאריך: [תאריך]
מס׳ חשבונית: [מספר]
```

- Send the **same file** to both numbers (two `sendFileByUpload` calls, or `sendFileByUrl` if
  the attachment already has a URL).
- Keep Karin's voice: concise, courteous, Hebrew RTL.
- If a send to one recipient fails, retry that one; report which recipient/invoice failed
  rather than silently dropping it.

## Step 5 — Mark as processed (no duplicates)

After **both** recipients received an invoice successfully, apply the Gmail label
**`PROCESSED_LABEL`** ("נשלח לרו״ח") to that email so it's never forwarded twice. If only one
recipient succeeded, do **not** mark it processed — leave it for a retry and say so.

## Step 6 — Confirm back to Karin

Give a one-line-per-invoice summary: what was forwarded, to whom, and anything that failed or
needs her attention (e.g. a missing number, a send that bounced). Example:

```
✅ הועברו 3 חשבוניות למעיין ולרו״ח:
• חח"י · 412₪ · 26/07 — נשלח לשניהם, סומן כטופל
• פרטנר · 89₪ · 25/07 — נשלח לשניהם, סומן כטופל
• ניירת · ? · 24/07 — לא נמצא מס׳ חשבונית, נשלח בכל זאת
```

## What "done" looks like

- Every invoice email (unprocessed, matching the rules) was found.
- Each invoice's file + Hebrew summary reached **both** Maayan and the accountant on WhatsApp.
- Confirmed with Karin first (unless auto-mode is on).
- Forwarded emails are labelled "נשלח לרו״ח" so nothing goes out twice.
- Any failure or missing detail was surfaced, not hidden.

## Optional — monthly digest

If Karin asks for a summary ("תני לי סיכום חשבוניות של החודש"), list every email labelled
"נשלח לרו״ח" for the period with ספק / סכום / תאריך and a total — no re-sending.
