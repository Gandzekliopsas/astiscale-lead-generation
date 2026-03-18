"""
Telegram notification bot for AstiScale lead generation system.

Setup:
1. Message @BotFather on Telegram → /newbot → copy the token
2. Set TELEGRAM_BOT_TOKEN env var in Railway
3. Start your bot → visit https://api.telegram.org/bot{TOKEN}/getUpdates → copy chat id
4. Set TELEGRAM_CHAT_ID env var in Railway

Notifications sent for: run completed, email opened, reply received, follow-up sent, weekly summary.
"""
import logging
import os
import requests

logger = logging.getLogger(__name__)

_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def is_configured() -> bool:
    return bool(_TOKEN and _CHAT_ID)


def send(message: str) -> bool:
    """Send HTML-formatted message to the configured Telegram chat."""
    global _TOKEN, _CHAT_ID
    _TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", _TOKEN)
    _CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", _CHAT_ID)
    if not is_configured():
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{_TOKEN}/sendMessage",
            json={"chat_id": _CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Telegram send error: {e}")
        return False


def notify_run_complete(city: str, industry: str, found: int, service: str):
    send(f"✅ <b>Paieška baigta</b>\n📍 {city.capitalize()} — {industry}\n🎯 {service}\n📋 Rasta: <b>{found}</b> leadų")


def notify_email_opened(company: str, open_count: int):
    send(f"👁 <b>El. laiškas atidarytas!</b>\n🏢 {company}\n🔢 Atidarytas {open_count}x\n💡 Geras laikas paskambinti!")


def notify_reply_received(company: str, from_email: str):
    send(f"🚨 <b>ATSAKĖ!</b>\n🏢 {company}\n📧 {from_email}\n⚡ Atsakyk kuo greičiau!")


def notify_followup_sent(company: str, followup_num: int):
    send(f"📤 <b>Follow-up #{followup_num} išsiųstas</b>\n🏢 {company}")


def notify_weekly_summary(total: int, sent: int, opens: int, replies: int):
    open_rate = f"{opens/sent*100:.0f}%" if sent else "0%"
    reply_rate = f"{replies/sent*100:.0f}%" if sent else "0%"
    send(
        f"📊 <b>Savaitės ataskaita</b>\n"
        f"📋 Leadai: {total} | 📤 Išsiųsta: {sent}\n"
        f"👁 Atidarymai: {opens} ({open_rate}) | 💬 Atsakymai: {replies} ({reply_rate})"
    )
