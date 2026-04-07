"""
Google Sheets 연동
- 헤더 자동 생성
- 고유ID 기준 중복 제거 (공고번호와 분리)
- 신규 항목만 추가
"""
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADERS = [
    "수집일시", "구분", "용역명", "추정가격(억원)", "입찰방식",
    "발주기관", "수요기관", "사전예고일", "공고일", "제안서제출마감",
    "위원추첨", "심사일", "개찰일시", "공고번호", "링크", "고유ID",
]

# 중복 체크에 사용하는 열 (고유ID, 0-based)
UNIQUE_ID_COL = HEADERS.index("고유ID")


def connect(credentials_file: str, sheet_id: str):
    creds  = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).sheet1


def ensure_headers(sheet) -> None:
    first = sheet.row_values(1)
    if first and first[0] == HEADERS[0]:
        return
    # 기존 데이터 전체 삭제 후 새 헤더로 시작 (구조 변경 시)
    sheet.clear()
    sheet.insert_row(HEADERS, 1)
    sheet.format("A1:P1", {
        "backgroundColor": {"red": 0.086, "green": 0.133, "blue": 0.243},
        "textFormat": {
            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
            "bold": True,
        },
        "horizontalAlignment": "CENTER",
    })
    # 고유ID 열 숨기기 (P열)
    sheet.spreadsheet.batch_update({
        "requests": [{
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet.id,
                    "dimension": "COLUMNS",
                    "startIndex": 15,   # P열 (0-based)
                    "endIndex": 16,
                },
                "properties": {"hiddenByUser": True},
                "fields": "hiddenByUser",
            }
        }]
    })


def get_existing_ids(sheet) -> set:
    col = sheet.col_values(UNIQUE_ID_COL + 1)   # gspread는 1-indexed
    return set(col[1:])                           # 헤더 제외


def append_new_items(sheet, items: list) -> list:
    existing  = get_existing_ids(sheet)
    new_items = [i for i in items if i.get("unique_id") not in existing]

    if not new_items:
        return []

    rows = [
        [
            item.get("collected_at", ""),
            item.get("type", ""),
            item.get("title", ""),
            item.get("amount_str", ""),
            item.get("bid_method", ""),
            item.get("org", ""),
            item.get("demand_org", ""),
            item.get("prenotice_dt", ""),
            item.get("announce_dt", ""),
            item.get("proposal_dt", ""),
            item.get("committee_dt", ""),
            item.get("review_dt", ""),
            item.get("open_dt", ""),
            item.get("bid_no", ""),       # 공고번호 (표시용, 깔끔한 번호)
            item.get("url", ""),
            item.get("unique_id", ""),    # 고유ID (중복확인용, 숨김 열)
        ]
        for item in new_items
    ]
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    return new_items
