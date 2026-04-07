"""
Gmail 이메일 알림 발송
"""
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GMAIL_USER, GMAIL_APP_PASSWORD, RECIPIENTS

TYPE_COLOR = {
    "발주계획": "#0F6E56",
    "사전규격": "#185FA5",
    "실공고":   "#8B1A1A",
}


def _badge(text: str, color: str) -> str:
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'background:{color}22;color:{color};font-size:11px;font-weight:600;">'
        f'{text}</span>'
    )


def _row(label: str, value: str) -> str:
    if not value or value == "-":
        return ""
    return (
        f'<tr><td style="color:#888;font-size:12px;padding:2px 8px 2px 0;'
        f'white-space:nowrap;">{label}</td>'
        f'<td style="font-size:12px;color:#333;">{value}</td></tr>'
    )


def _card(item: dict) -> str:
    t = item.get("type", "")
    color = TYPE_COLOR.get(t, "#555")
    rows_html = "".join([
        _row("추정가격",      item.get("amount_str", "")),
        _row("입찰방식",      item.get("bid_method", "")),
        _row("발주기관",      item.get("org", "")),
        _row("수요기관",      item.get("demand_org", "")),
        _row("사전예고",      item.get("prenotice_dt", "")),
        _row("공고일",        item.get("announce_dt", "")),
        _row("제안서마감",    item.get("proposal_dt", "")),
        _row("위원추첨",      item.get("committee_dt", "")),
        _row("심사",          item.get("review_dt", "")),
        _row("개찰",          item.get("open_dt", "")),
    ])
    url = item.get("url", "#")
    return f"""
<div style="border:1px solid #e0e0e0;border-radius:8px;padding:14px 16px;
            margin-bottom:10px;background:#fff;">
  <div style="margin-bottom:8px;">
    {_badge(t, color)}
    <span style="font-size:14px;font-weight:600;color:#1a1a1a;
                 margin-left:6px;">{item.get("title","")}</span>
  </div>
  <table style="border-collapse:collapse;">{rows_html}</table>
  <div style="margin-top:10px;">
    <a href="{url}" style="display:inline-block;padding:5px 14px;
       background:#E6F1FB;color:#0C447C;border-radius:5px;
       font-size:12px;font-weight:500;text-decoration:none;">공고 원문 보기</a>
  </div>
</div>"""


def build_html(items: list, run_time: str) -> str:
    cards = "".join(_card(i) for i in items)
    cnt = {t: sum(1 for i in items if i.get("type") == t)
           for t in ["발주계획", "사전규격", "실공고"]}
    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'맑은 고딕',sans-serif;">
<div style="max-width:680px;margin:20px auto;">

  <div style="background:#16213e;border-radius:10px 10px 0 0;padding:18px 24px;">
    <div style="font-size:18px;font-weight:600;color:#fff;">PQ 공고 모니터링</div>
    <div style="font-size:12px;color:#8888aa;margin-top:3px;">{run_time} 기준</div>
  </div>

  <div style="background:#fff;padding:14px 24px;display:flex;gap:10px;
              border-bottom:1px solid #eee;">
    <div style="flex:1;text-align:center;padding:10px;background:#f9f9f9;border-radius:6px;">
      <div style="font-size:22px;font-weight:700;color:#16213e;">{len(items)}</div>
      <div style="font-size:11px;color:#888;">신규 전체</div>
    </div>
    <div style="flex:1;text-align:center;padding:10px;background:#f9f9f9;border-radius:6px;">
      <div style="font-size:22px;font-weight:700;color:#0F6E56;">{cnt["발주계획"]}</div>
      <div style="font-size:11px;color:#888;">발주계획</div>
    </div>
    <div style="flex:1;text-align:center;padding:10px;background:#f9f9f9;border-radius:6px;">
      <div style="font-size:22px;font-weight:700;color:#185FA5;">{cnt["사전규격"]}</div>
      <div style="font-size:11px;color:#888;">사전규격</div>
    </div>
    <div style="flex:1;text-align:center;padding:10px;background:#f9f9f9;border-radius:6px;">
      <div style="font-size:22px;font-weight:700;color:#8B1A1A;">{cnt["실공고"]}</div>
      <div style="font-size:11px;color:#888;">실공고</div>
    </div>
  </div>

  <div style="background:#fff;padding:16px 24px 20px;border-radius:0 0 10px 10px;">
    {cards}
  </div>

  <div style="text-align:center;padding:12px;font-size:11px;color:#aaa;">
    자동 수집 · 06:00 / 09:00 / 12:00 / 15:00 / 18:00 (KST)
  </div>
</div>
</body></html>"""


def send(items: list) -> None:
    run_time = datetime.now().strftime("%Y.%m.%d %H:%M")
    subject  = f"[PQ 알림] 신규 공고 {len(items)}건 — {run_time}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(build_html(items, run_time), "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        s.sendmail(GMAIL_USER, RECIPIENTS, msg.as_bytes())
    print(f"[메일] 발송 완료 → {RECIPIENTS} / {len(items)}건")
