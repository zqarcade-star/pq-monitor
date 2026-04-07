"""
Google Sheets 연동
- 헤더 완전 일치 확인 후 불일치 시 초기화
- 고유ID 기준 중복 제거
- 링크는 HYPERLINK 수식으로 클릭 가능하게
"""
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ── 시트 열 구조 (A~N) ────────────────────────────────────────
HEADERS = [
    "구분",       # A
    "용역명",     # B
    "추정금액",   # C
    "입찰방식",   # D
    "발주기관",   # E
    "수요기관",   # F
    "사전예고일", # G
    "공고일",     # H
    "마감일",     # I  (제안서/입찰마감)
    "개찰일",     # J
    "공고번호",   # K
    "링크",       # L
    "수집시각",   # M
    "고유ID",     # N  (중복확인용, 숨김)
]

UNIQUE_ID_COL = HEADERS.index("고유ID") + 1   # gspread 1-indexed → 14


def connect(credentials_file: str, sheet_id: str):
    creds  = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).sheet1


def ensure_headers(sheet) -> None:
    """헤더가 정확히 일치하지 않으면 시트 전체 초기화 후 재생성"""
    current = sheet.row_values(1)
    if current == HEADERS:
        return

    print("[시트] 헤더 구조 변경 감지 → 초기화 후 재생성")
    sheet.clear()
    sheet.append_row(HEADERS)

    # 헤더 행 스타일
    sheet.format("A1:N1", {
        "backgroundColor": {"red": 0.086, "green": 0.133, "blue": 0.243},
        "textFormat": {
            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
            "bold": True,
        },
        "horizontalAlignment": "CENTER",
    })

    # 고유ID 열(N) 숨기기
    try:
        sheet.spreadsheet.batch_update({"requests": [{
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet.id,
                    "dimension": "COLUMNS",
                    "startIndex": 13,   # N열 (0-based)
                    "endIndex": 14,
                },
                "properties": {"hiddenByUser": True},
                "fields": "hiddenByUser",
            }
        }]})
    except Exception as e:
        print(f"[시트] 열 숨기기 실패(무시): {e}")


def get_existing_ids(sheet) -> set:
    col = sheet.col_values(UNIQUE_ID_COL)
    return set(col[1:])   # 헤더 제외


def append_new_items(sheet, items: list) -> list:
    existing  = get_existing_ids(sheet)
    new_items = [i for i in items if i.get("unique_id") not in existing]

    if not new_items:
        return []

    rows = []
    for item in new_items:
        url = item.get("url", "")
        link = f'=HYPERLINK("{url}","열기")' if url else ""
        rows.append([
            item.get("type", ""),
            item.get("title", ""),
            item.get("amount_str", ""),
            item.get("bid_method", ""),
            item.get("org", ""),
            item.get("demand_org", ""),
            item.get("prenotice_dt", ""),
            item.get("announce_dt", ""),
            item.get("proposal_dt", ""),
            item.get("open_dt", ""),
            item.get("bid_no", ""),
            link,
            item.get("collected_at", ""),
            item.get("unique_id", ""),
        ])

    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    return new_items
