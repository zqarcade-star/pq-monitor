import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── 나라장터 OpenAPI ──────────────────────────────────────────
G2B_API_KEY        = os.environ.get("G2B_API_KEY", "")

# ── 금액 필터 (단위: 원) ──────────────────────────────────────
AMOUNT_THRESHOLD   = 15_0000_0000   # 15억원

# ── Gmail 발신 ───────────────────────────────────────────────
GMAIL_USER         = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# ── 수신자 목록 ──────────────────────────────────────────────
RECIPIENTS = [
    r.strip()
    for r in os.environ.get("RECIPIENTS", "").split(",")
    if r.strip()
]

# ── Google Sheets ─────────────────────────────────────────────
SHEET_ID          = os.environ.get("SHEET_ID", "")
CREDENTIALS_FILE  = os.environ.get("CREDENTIALS_FILE", "credentials.json")

# ── 경로 ─────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "logs", "run.log")
