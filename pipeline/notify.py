import os

import requests


def enabled():
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def compose(filings, moves, app_url):
    lines = []
    if filings:
        lines.append(f"<b>{len(filings)} filing{'s' if len(filings) > 1 else ''} need you</b>")
        for f in filings[:6]:
            body = f.get("summary") or f.get("title") or f.get("subject")
            lines.append(f"• <b>{_esc(f['symbol'])}</b> {_esc(f['why'])}: {_esc(body)[:160]}")
    if moves:
        if lines:
            lines.append("")
        lines.append("<b>Moves past your lines</b>")
        for m in moves[:8]:
            bits = [f"{m['ret']:+.1f}%"]
            if m.get("vol_x") and "volume" in m["why"]:
                bits.append(f"{m['vol_x']:.1f}× volume")
            lines.append(f"• <b>{_esc(m['symbol'])}</b> {', '.join(bits)} on {m['date']}")
    if not lines:
        return None
    if app_url:
        lines.append("")
        lines.append(f'<a href="{app_url}">Open FINN</a>')
    return "\n".join(lines)


def send(text):
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    r = requests.post(
        f"https://api.telegram.org/bot{tok}/sendMessage",
        json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=20,
    )
    r.raise_for_status()
