import os, sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from crawlers.g2b      import collect_all
from filters.rules     import filter_items
from storage.sheets    import connect, ensure_headers, append_new_items
from config            import LOG_FILE, SHEET_ID, CREDENTIALS_FILE


def log(msg: str) -> None:
    ts   = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> None:
    log("=" * 55)
    log("PQ 모니터링 시작")

    # 1. 나라장터 수집
    log("나라장터 수집 중...")
    raw = collect_all()
    log(f"  수집: {len(raw)}건")

    # 2. 필터 (15억 이상 + 건설사업관리 키워드)
    filtered = filter_items(raw)
    log(f"  필터 후: {len(filtered)}건")

    if not filtered:
        log("해당 공고 없음 — 종료")
        return

    # 3. Google Sheets 중복 제거 후 신규만 추가
    log("Google Sheets 업데이트 중...")
    sheet     = connect(CREDENTIALS_FILE, SHEET_ID)
    ensure_headers(sheet)
    new_items = append_new_items(sheet, filtered)
    log(f"  신규 추가: {len(new_items)}건")

    log("완료")


if __name__ == "__main__":
    main()
