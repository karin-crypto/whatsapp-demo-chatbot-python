"""Forward an email invoice (PDF) to WhatsApp via Green API.

This is the "sending hand" behind the `karin-keren-forward-invoices` skill. It solves
the two pieces that a chat session cannot do on its own:

1. Download the actual PDF *bytes* of an invoice attachment from Gmail (the Gmail chat
   connector only exposes text, not attachment content).
2. Send that PDF over WhatsApp with `sendFileByUpload` through Green API instance 7107653407.

It can also skip Gmail entirely and just send a local PDF file you already have.

--------------------------------------------------------------------------------
Credentials (set as environment variables — never hard-code secrets):

  GREENAPI_ID_INSTANCE     Green API instance id (e.g. 7107653407)
  GREENAPI_API_TOKEN       Green API instance api token

  For Gmail download mode you also need standard Google OAuth credentials:
  GOOGLE_OAUTH_CLIENT       path to the OAuth client secret json (default: credentials.json)
  GOOGLE_OAUTH_TOKEN        path to the cached user token json    (default: token.json)
  The first run opens a browser once to authorise read-only Gmail access.

--------------------------------------------------------------------------------
Usage:

  # 1) Send a local PDF you already saved:
  python tools/forward_invoice_whatsapp.py --file receipt.pdf \
      --caption "חשבונית הובלה" --to accountant

  # 2) Pull the PDF straight from a Gmail message and forward it:
  python tools/forward_invoice_whatsapp.py --gmail-message-id 19f92f84eac6905a \
      --to accountant

  --to accepts: accountant | maayan | both | a raw number like 972559734494
                (repeat --to to send to several targets)
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import tempfile

from whatsapp_api_client_python import API

# --- Recipients (keep in sync with the skill's config block) --------------------
RECIPIENTS = {
    "maayan": "972532248724",      # מעיין, מנהלת משרד (053-2248724)
    "accountant": "972559734494",  # ספואן נג'אר, רו"ח (055-9734494)
}


def resolve_targets(values: list[str]) -> list[str]:
    """Turn --to values (accountant/maayan/both/<number>) into E.164 digit strings."""
    numbers: list[str] = []
    for value in values:
        key = value.strip().lower()
        if key == "both":
            numbers.extend(RECIPIENTS.values())
        elif key in RECIPIENTS:
            numbers.append(RECIPIENTS[key])
        elif key.isdigit():
            numbers.append(key)
        else:
            sys.exit(f"Unknown --to target: {value!r} (use accountant/maayan/both/<number>)")
    # de-duplicate while preserving order
    return list(dict.fromkeys(numbers))


def download_gmail_attachment(message_id: str) -> str:
    """Download the first PDF attachment of a Gmail message; return the local file path.

    Uses read-only Gmail API access. Imported lazily so local-file mode has no
    Google dependency.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
    token_path = os.getenv("GOOGLE_OAUTH_TOKEN", "token.json")
    client_path = os.getenv("GOOGLE_OAUTH_CLIENT", "credentials.json")

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_path, scopes)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf8") as token_file:
            token_file.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    message = service.users().messages().get(userId="me", id=message_id).execute()

    for part in message.get("payload", {}).get("parts", []):
        filename = part.get("filename", "")
        body = part.get("body", {})
        if filename.lower().endswith(".pdf") and body.get("attachmentId"):
            attachment = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=body["attachmentId"])
                .execute()
            )
            data = base64.urlsafe_b64decode(attachment["data"])
            out_path = os.path.join(tempfile.gettempdir(), filename)
            with open(out_path, "wb") as out_file:
                out_file.write(data)
            return out_path

    sys.exit(f"No PDF attachment found on Gmail message {message_id}")


def send_pdf(path: str, numbers: list[str], caption: str) -> None:
    """Send one PDF to each WhatsApp number via Green API sendFileByUpload."""
    id_instance = os.getenv("GREENAPI_ID_INSTANCE")
    api_token = os.getenv("GREENAPI_API_TOKEN")
    if not id_instance or not api_token:
        sys.exit("Missing GREENAPI_ID_INSTANCE / GREENAPI_API_TOKEN environment variables")

    green_api = API.GreenAPI(id_instance, api_token)
    filename = os.path.basename(path)

    for number in numbers:
        chat_id = f"{number}@c.us"
        response = green_api.sending.sendFileByUpload(chat_id, path, filename, caption)
        ok = getattr(response, "code", None) == 200
        print(f"{'✅' if ok else '❌'} {number}: {getattr(response, 'text', response)}")
        if not ok:
            print(f"   send to {number} failed — retry this recipient", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Forward an invoice PDF to WhatsApp via Green API.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="Path to a local PDF to send.")
    source.add_argument("--gmail-message-id", help="Gmail message id to pull the PDF from.")
    parser.add_argument(
        "--to",
        action="append",
        required=True,
        help="Recipient: accountant | maayan | both | <number>. Repeatable.",
    )
    parser.add_argument("--caption", default="", help="Optional WhatsApp caption text.")
    args = parser.parse_args()

    numbers = resolve_targets(args.to)
    path = args.file if args.file else download_gmail_attachment(args.gmail_message_id)
    send_pdf(path, numbers, args.caption)


if __name__ == "__main__":
    main()
