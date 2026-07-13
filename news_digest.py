"""Fetch top Indian headlines from NewsAPI and send a daily digest email.

Usage:
    python news_digest.py              # defaults to yesterday
    python news_digest.py 2026-07-12   # specific date (YYYY-MM-DD)
"""

import logging
import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_NEWSAPI_EVERYTHING = "https://newsapi.org/v2/everything"

_SECTIONS = [
    ("Top Stories",    "india",          "#2c3e50"),
    ("Business",       "business india", "#2980b9"),
    ("Technology",     "technology india","#8e44ad"),
    ("Science",        "science india",  "#16a085"),
    ("Health",         "health india",   "#27ae60"),
    ("Sports",         "sports india",   "#e67e22"),
    ("Entertainment",  "bollywood OR cricket entertainment india", "#c0392b"),
]


def _fetch_articles(api_key: str, query: str, date: datetime, page_size: int = 5) -> list[dict]:
    date_str = date.strftime("%Y-%m-%d")
    try:
        r = requests.get(
            _NEWSAPI_EVERYTHING,
            params={
                "q": query,
                "from": date_str,
                "to": date_str,
                "sortBy": "popularity",
                "pageSize": page_size,
                "language": "en",
                "apiKey": api_key,
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("articles", [])
    except Exception as e:
        logger.warning(f"Failed to fetch '{query}' articles: {e}")
        return []


def _article_html(article: dict) -> str:
    title = article.get("title") or ""
    desc = article.get("description") or ""
    url = article.get("url") or "#"
    source = (article.get("source") or {}).get("name") or ""

    if " - " in title and title.endswith(source):
        title = title[: title.rfind(" - ")].strip()

    desc_html = f"<p style='margin:4px 0 0 0;color:#555;font-size:13px;'>{desc}</p>" if desc else ""
    source_html = (
        f"<span style='font-size:11px;color:#999;text-transform:uppercase;"
        f"letter-spacing:0.5px;'>{source}</span>&nbsp;"
        if source else ""
    )
    return (
        f"<li style='margin-bottom:14px;list-style:none;padding:0;'>"
        f"<div style='font-size:11px;color:#aaa;margin-bottom:2px;'>{source_html}</div>"
        f"<a href='{url}' style='font-size:14px;font-weight:600;color:#222;"
        f"text-decoration:none;line-height:1.4;'>{title}</a>"
        f"{desc_html}"
        f"</li>"
    )


def _section_html(label: str, color: str, articles: list[dict]) -> str:
    if not articles:
        return ""
    items = "".join(_article_html(a) for a in articles)
    return (
        f"<div style='margin-bottom:28px;'>"
        f"<h3 style='margin:0 0 12px 0;padding:6px 12px;background:{color};color:white;"
        f"font-size:13px;letter-spacing:1px;text-transform:uppercase;border-radius:3px;'>"
        f"{label}</h3>"
        f"<ul style='margin:0;padding:0 0 0 4px;'>{items}</ul>"
        f"</div>"
    )


def _section_text(label: str, articles: list[dict]) -> str:
    if not articles:
        return ""
    lines = [f"\n{label.upper()}", "─" * 40]
    for a in articles:
        title = a.get("title") or ""
        source = (a.get("source") or {}).get("name") or ""
        if source and title.endswith(source):
            title = title[: title.rfind(" - ")].strip()
        lines.append(f"• {title}")
        if a.get("url"):
            lines.append(f"  {a['url']}")
    return "\n".join(lines)


def build_digest(api_key: str, date: datetime) -> tuple[str, str]:
    """Returns (html_body, text_body) for the given date."""
    date_label = date.strftime("%A, %d %B %Y")
    sections_html = []
    sections_text = []

    for label, query, color in _SECTIONS:
        articles = _fetch_articles(api_key, query, date)
        sections_html.append(_section_html(label, color, articles))
        sections_text.append(_section_text(label, articles))

    body_html = (
        f"<html><body style='font-family:Georgia,serif;max-width:640px;margin:0 auto;padding:20px;'>"
        f"<div style='border-bottom:3px solid #2c3e50;padding-bottom:12px;margin-bottom:24px;'>"
        f"<h1 style='margin:0;font-size:22px;color:#2c3e50;'>Your Daily News Digest</h1>"
        f"<p style='margin:4px 0 0 0;color:#888;font-size:13px;'>{date_label}</p>"
        f"</div>"
        f"{''.join(sections_html)}"
        f"<p style='font-size:11px;color:#bbb;border-top:1px solid #eee;padding-top:12px;margin-top:8px;'>"
        f"Powered by NewsAPI &middot; Delivered via GitHub Actions"
        f"</p></body></html>"
    )
    body_text = (
        f"Your Daily News Digest — {date_label}\n"
        + "=" * 50
        + "\n".join(sections_text)
    )
    return body_html, body_text


def send_digest(date: datetime) -> None:
    api_key = os.environ.get("NEWS_API_KEY", "")
    email_from = os.environ.get("GMAIL_ADDRESS", "")
    email_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    email_to = os.environ.get("NOTIFY_EMAIL", "harimanjunath@gmail.com")

    if not api_key:
        logger.error("NEWS_API_KEY is not set — aborting.")
        return
    if not email_from or not email_password:
        logger.error("GMAIL_ADDRESS or GMAIL_APP_PASSWORD is not set — aborting.")
        return

    logger.info(f"Fetching headlines for {date.strftime('%Y-%m-%d')}…")
    html_body, text_body = build_digest(api_key, date)

    subject = f"Daily News Digest — {date.strftime('%d %b %Y')}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(email_from, email_password)
        server.sendmail(email_from, email_to, msg.as_string())

    logger.info(f"Digest sent to {email_to}: {subject}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            target_date = datetime.strptime(sys.argv[1], "%Y-%m-%d")
        except ValueError:
            print(f"Invalid date '{sys.argv[1]}' — expected YYYY-MM-DD")
            sys.exit(1)
    else:
        target_date = datetime.today() - timedelta(days=1)

    send_digest(target_date)
