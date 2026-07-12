"""Email notifications via Gmail SMTP (app password auth)."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO

logger = logging.getLogger(__name__)

_GREEN = "#27ae60"
_ORANGE = "#e67e22"
_RED = "#c0392b"


def _seats_color(seats: int) -> str:
    if seats > 60:
        return _GREEN
    if seats > 20:
        return _ORANGE
    return _RED


def _send(subject: str, body_html: str, body_text: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    logger.info(f"Email sent: {subject}")


def send_threshold_alert(
    *,
    route_name: str,
    train_no: str,
    train_name: str,
    travel_date: str,
    departure: str,
    cls: str,
    seats_available: int,
    threshold: int,
) -> None:
    subject = (
        f"[Train Alert] {seats_available} seats left — "
        f"{route_name} | {train_name} | {travel_date} | {cls}"
    )
    color = _seats_color(seats_available)

    text = (
        f"Train Seat Alert\n"
        f"{'─' * 40}\n"
        f"Route      : {route_name}\n"
        f"Train      : {train_no} {train_name}\n"
        f"Date       : {travel_date}\n"
        f"Departure  : {departure}\n"
        f"Class      : {cls}\n"
        f"Seats Left : {seats_available}  (threshold: ≤{threshold})\n\n"
        f"Book now: https://www.irctc.co.in\n"
    )

    html = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <h2 style="color:{color};">&#9888; Train Seat Alert</h2>
  <table style="border-collapse:collapse;width:100%;font-size:14px;">
    <tr style="background:#f5f5f5;">
      <td style="padding:8px 12px;font-weight:bold;width:140px;">Route</td>
      <td style="padding:8px 12px;">{route_name}</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;font-weight:bold;">Train</td>
      <td style="padding:8px 12px;">{train_no} — {train_name}</td>
    </tr>
    <tr style="background:#f5f5f5;">
      <td style="padding:8px 12px;font-weight:bold;">Date</td>
      <td style="padding:8px 12px;">{travel_date}</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;font-weight:bold;">Departure</td>
      <td style="padding:8px 12px;">{departure}</td>
    </tr>
    <tr style="background:#f5f5f5;">
      <td style="padding:8px 12px;font-weight:bold;">Class</td>
      <td style="padding:8px 12px;">{cls}</td>
    </tr>
    <tr>
      <td style="padding:8px 12px;font-weight:bold;">Seats Left</td>
      <td style="padding:8px 12px;">
        <span style="color:{color};font-size:1.4em;font-weight:bold;">{seats_available}</span>
        <span style="color:#888;font-size:0.85em;"> (alert threshold: ≤{threshold} seats)</span>
      </td>
    </tr>
  </table>
  <p style="margin-top:20px;">
    <a href="https://www.irctc.co.in"
       style="background:{color};color:white;padding:10px 20px;text-decoration:none;border-radius:4px;display:inline-block;">
      Book on IRCTC &rarr;
    </a>
  </p>
</body></html>
"""
    _send(subject, html, text)


def send_daily_digest(today_str: str, rows: list[dict]) -> None:
    """
    rows: list of dicts with keys:
      date, route, train_no, train_name, departure, cls, seats
    """
    subject = f"[Train Digest] Daily Availability — {today_str}"

    text_lines = [f"Daily Train Availability Digest — {today_str}", "=" * 70]
    for r in rows:
        text_lines.append(
            f"{r['date']:15} | {r['route']:25} | {r['train_no']} {r['train_name']:20} "
            f"| Dep {r['departure']} | {r['cls']:3} | {r['seats']} seats available"
        )
    if not rows:
        text_lines.append("No trains found for the monitored routes in the next 14 days.")
    text_lines.append("\nBook on IRCTC: https://www.irctc.co.in")
    body_text = "\n".join(text_lines)

    def row_html(r: dict) -> str:
        color = _seats_color(r["seats"])
        return (
            f"<tr>"
            f"<td style='padding:6px 10px;'>{r['date']}</td>"
            f"<td style='padding:6px 10px;'>{r['route']}</td>"
            f"<td style='padding:6px 10px;'>{r['train_no']} {r['train_name']}</td>"
            f"<td style='padding:6px 10px;'>{r['departure']}</td>"
            f"<td style='padding:6px 10px;font-weight:bold;'>{r['cls']}</td>"
            f"<td style='padding:6px 10px;color:{color};font-weight:bold;font-size:1.1em;'>{r['seats']}</td>"
            f"</tr>"
        )

    rows_html = "".join(row_html(r) for r in rows) if rows else (
        "<tr><td colspan='6' style='text-align:center;padding:16px;color:#888;'>"
        "No trains found for the monitored routes in the next 14 days.</td></tr>"
    )

    html = f"""
<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;">
  <h2 style="color:#333;">Daily Train Availability Digest</h2>
  <p style="color:#666;margin-top:-10px;">{today_str}</p>
  <table border="1" style="border-collapse:collapse;width:100%;font-size:13px;">
    <thead>
      <tr style="background:#333;color:white;">
        <th style="padding:8px 10px;">Date</th>
        <th style="padding:8px 10px;">Route</th>
        <th style="padding:8px 10px;">Train</th>
        <th style="padding:8px 10px;">Departure</th>
        <th style="padding:8px 10px;">Class</th>
        <th style="padding:8px 10px;">Seats Available</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
  <p style="font-size:12px;color:#999;margin-top:12px;">
    <span style="color:{_GREEN};">&#9679;</span> &gt;60 seats &nbsp;
    <span style="color:{_ORANGE};">&#9679;</span> 21–60 seats &nbsp;
    <span style="color:{_RED};">&#9679;</span> &#8804;20 seats
  </p>
  <p><a href="https://www.irctc.co.in" style="color:#333;">Book on IRCTC &rarr;</a></p>
</body></html>
"""
    _send(subject, html, body_text)
