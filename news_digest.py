"""Fetch top Indian headlines from NewsAPI and send a daily digest email."""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_NEWSAPI_BASE = "https://newsapi.org/v2/top-headlines"

_CATEGORIES = [
    ("general",       "Top Stories"),
    ("business",      "Business"),
    ("technology",    "Technology"),
    ("science",       "Science"),
    ("health",        "Health"),
    ("sports",        "Sports"),
    ("entertainment", "Entertainment"),
]

_CATEGORY_COLORS = {
    "general":       "#2c3e50",
    "business":      "#2980b9",
    "technology":    "#8e44ad",
    "science":       "#16a085",
    "health":        "#27ae60",
    "sports":        "#e67e22",
    "entertainment": "#c0392b",
}


def _fetch_headlines(api_key: str, category: str, page_size: int = 5) -> list[dict]:
    try:
        r = requests.get(
            _NEWSAPI_BASE,
            params={
                "country": "in",
                "category": category,
                "pageSize": page_size,
                "apiKey": api_key,
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("articles", [])
    except Exception as e:
        logger.warning(f"Failed to fetch {category} headlines: {e}")
        return []


def _article_html(article: dict) -> str:
    title = article.get("title") or ""
    desc = article.get("description") or ""
    url = article.get("url") or "#"
    source = (article.get("source") or {}).get("name") or ""

    # Strip the source name appended after " - " in many NewsAPI titles
    if " - " in title and title.endswith(source):
        title = title[: title.rfind(" - ")].strip()

    desc_html = f"<p style='margin:4px 0 0 0;color:#555;font-size:13px;'>{desc}</p>" if desc else ""
    source_html = (
        f"<span style='font-size:11px;color:#999;text-transform:uppercase;"
        f"letter-spacing:0.5px;'>{source}</span> &nbsp;"
        if source
        else ""
    )
    return f"""
    <li style='margin-bottom:14px;list-style:none;padding:0;'>
      <div style='font-size:11px;color:#aaa;margin-bottom:2px;'>{source_html}</div>
      <a href='{url}' style='font-size:14px;font-weight:600;color:#222;text-decoration:none;
         line-height:1.4;'>
        {title}
      </a>
      {desc_html}
    </li>"""


def _section_html(label: str, color: str, articles: list[dict]) -> str:
    if not articles:
        return ""
    items = "".join(_article_html(a) for a in articles)
    return f"""
  <div style='margin-bottom:28px;'>
    <h3 style='margin:0 0 12px 0;padding:6px 12px;background:{color};color:white;
               font-size:13px;letter-spacing:1px;text-transform:uppercase;
               border-radius:3px;'>{label}</h3>
    <ul style='margin:0;padding:0 0 0 4px;'>
      {items}
    </ul>
  </div>"""


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


def build_digest(api_key: str) -> tuple[str, str]:
    """Returns (html_body, text_body)."""
    date_label = datetime.now().strftime("%A, %d %B %Y")
    sections_html = []
    sections_text = []

    for category, label in _CATEGORIES:
        articles = _fetch_headlines(api_key, category)
        color = _CATEGORY_COLORS[category]
        sections_html.append(_section_html(label, color, articles))
        sections_text.append(_section_text(label, articles))

    body_html = f"""
<html><body style='font-family:Georgia,serif;max-width:640px;margin:0 auto;padding:20px;'>
  <div style='border-bottom:3px solid #2c3e50;padding-bottom:12px;margin-bottom:24px;'>
    <h1 style='margin:0;font-size:22px;color:#2c3e50;'>Your Daily News Digest</h1>
    <p style='margin:4px 0 0 0;color:#888;font-size:13px;'>{date_label}</p>
  </div>
  {"".join(sections_html)}
  <p style='font-size:11px;color:#bbb;border-top:1px solid #eee;padding-top:12px;margin-top:8px;'>
    Powered by NewsAPI &middot; Delivered via GitHub Actions
  </p>
</body></html>"""

    body_text = f"Your Daily News Digest — {date_label}\n" + "=" * 50 + "\n".join(sections_text)
    return body_html, body_text


def send_digest() -> None:
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

    logger.info("Fetching headlines from NewsAPI…")
    html_body, text_body = build_digest(api_key)

    date_label = datetime.now().strftime("%d %b %Y")
    subject = f"Daily News Digest — {date_label}"

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
    send_digest()
