"""
Google Sheets 연동
- 헤더 완전 일치 확인 후 불일치 시 초기화
- 고유ID 기준 중복 제거
- 링크는 HYPERLINK 수식으로 클릭 가능하게
"""
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ── 시트 열 구조 (A~L, 12열) ──────────────────────────────────
HEADERS = [
    "수집시간",   # A  (KST)
    "공고종류",   # B
    "차수",       # C
    "공고번호",   # D
    "공고명",     # E
    "추정가격",   # F
    "공고기관",   # G
    "수요기관",   # H
    "게시일",     # I  (날짜+시간, 사전규격=공개일시 / 실공고=공고일시)
    "개찰일",     # J
    "링크",       # K
    "고유ID",     # L  (중복확인용, 숨김)
]

LAST_COL      = "L"
HEADER_RANGE  = f"A1:{LAST_COL}1"
UNIQUE_ID_COL = len(HEADERS)   # gspread 1-indexed → 12


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
    sheet.format(HEADER_RANGE, {
        "backgroundColor": {"red": 0.086, "green": 0.133, "blue": 0.243},
        "textFormat": {
            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
            "bold": True,
        },
        "horizontalAlignment": "CENTER",
    })

    # 고유ID 열(L) 숨기기
    try:
        sheet.spreadsheet.batch_update({"requests": [{
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet.id,
                    "dimension": "COLUMNS",
                    "startIndex": 11,   # L열 (0-based)
                    "endIndex":   12,
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
        url  = item.get("url", "")
        link = f'=HYPERLINK("{url}","열기")' if url else ""
        rows.append([
            item.get("collected_at", ""),   # A 수집시간
            item.get("ntce_kind", ""),      # B 공고종류
            item.get("bid_seq", ""),        # C 차수
            item.get("bid_no", ""),         # D 공고번호
            item.get("title", ""),          # E 공고명
            item.get("amount_str", ""),     # F 추정가격
            item.get("org", ""),            # G 공고기관
            item.get("demand_org", ""),     # H 수요기관
            item.get("announce_dt", ""),    # I 공고일 (시간 포함)
            item.get("open_dt", ""),        # J 개찰일
            link,                           # K 링크
            item.get("unique_id", ""),      # L 고유ID
        ])

    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    return new_items
