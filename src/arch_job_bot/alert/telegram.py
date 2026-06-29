"""Telegram Bot API sender (primary channel).

Uses only the stdlib so delivery never depends on the scraping stack. Setup:
  1. message @BotFather -> /newbot -> copy the token into TELEGRAM_BOT_TOKEN
  2. she opens the bot and taps Start
  3. run `python -m arch_job_bot.alert.telegram <token>` to print her chat_id
  4. put it in TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"


class TelegramSender:
    def __init__(self, token: str, chat_id: str, *, timeout: float = 15.0):
        if not token or not chat_id:
            raise ValueError("TelegramSender requires both token and chat_id")
        self.token = token
        self.chat_id = str(chat_id)
        self.timeout = timeout

    def _post(self, method: str, payload: dict) -> dict:
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def send(self, text: str, *, html: bool = True, preview: bool = True) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": "false" if preview else "true",
        }
        if html:
            payload["parse_mode"] = "HTML"
        try:
            res = self._post("sendMessage", payload)
            if not res.get("ok"):
                log.error("Telegram sendMessage not ok: %s", res)
                return False
            return True
        except urllib.error.HTTPError as e:
            log.error("Telegram HTTPError %s: %s", e.code, e.read().decode("utf-8", "ignore"))
        except Exception as e:  # noqa: BLE001 — delivery must never crash the loop
            log.error("Telegram send failed: %s", e)
        return False


def print_chat_id(token: str) -> None:
    """Helper: print recent chat ids so you can grab hers after she taps Start."""
    url = API.format(token=token, method="getUpdates")
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    seen = {}
    for upd in data.get("result", []):
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            seen[chat["id"]] = chat.get("first_name") or chat.get("title") or chat.get("username") or "?"
    if not seen:
        print("No chats yet. Have her open the bot and tap Start, then re-run.")
    for cid, name in seen.items():
        print(f"chat_id={cid}  ({name})")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: python -m arch_job_bot.alert.telegram <BOT_TOKEN>")
        raise SystemExit(2)
    print_chat_id(sys.argv[1])
