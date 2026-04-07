"""
Google Sheets 연동
- 헤더 완전 일치 확인 후 불일치 시 초기화
- 고유ID 기준 중복 제거
- 링크는 HYPERLINK 수식으로 클릭 가능하게
"""
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ── 시트 열 구조 (A~W, 23열) ──────────────────────────────────
HEADERS = [
    "공고종류",       # A  (ntceKindNm - G2B 원본값)
    "공고명",         # B
    "추정가격",       # C
    "낙찰방법",       # D  (sucsfbidMthdNm)
    "입찰방법",       # E  (bidMethdNm)
    "공고기관",       # F
    "수요기관",       # G
    "PQ여부",         # H
    "기술제안",       # I
    "현장설명",       # J
    "공고일",         # K
    "입찰시작",       # L
    "제안서마감",     # M
    "PQ서류마감",     # N
    "기술제안마감",   # O
    "현장설명일",     # P
    "개찰일",         # Q
    "실적서류마감",   # R
    "공고번호",       # S
    "차수",           # T
    "링크",           # U
    "수집시각",       # V
    "고유ID",         # W  (중복확인용, 숨김)
]

LAST_COL      = "W"
HEADER_RANGE  = f"A1:{LAST_COL}1"
UNIQUE_ID_COL = len(HEADERS)   # gspread 1-indexed → 23


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

    # 고유ID 열(W) 숨기기
    try:
        sheet.spreadsheet.batch_update({"requests": [{
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet.id,
                    "dimension": "COLUMNS",
                    "startIndex": 22,   # W열 (0-based)
                    "endIndex": 23,
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
            item.get("ntce_kind", ""),          # A 공고종류
            item.get("title", ""),              # B 공고명
            item.get("amount_str", ""),         # C 추정가격
            item.get("sucsfbid_mthd", ""),      # D 낙찰방법
            item.get("bid_mthd", ""),           # E 입찰방법
            item.get("org", ""),                # F 공고기관
            item.get("demand_org", ""),         # G 수요기관
            item.get("pq_yn", ""),              # H PQ여부
            item.get("tp_eval_yn", ""),         # I 기술제안
            item.get("site_yn", ""),            # J 현장설명
            item.get("announce_dt", ""),        # K 공고일
            item.get("bid_begin_dt", ""),       # L 입찰시작
            item.get("bid_close_dt", ""),       # M 제안서마감
            item.get("pq_rcpt_dt", ""),         # N PQ서류마감
            item.get("tp_close_dt", ""),        # O 기술제안마감
            item.get("site_dt", ""),            # P 현장설명일
            item.get("open_dt", ""),            # Q 개찰일
            item.get("arslt_rcpt_dt", ""),      # R 실적서류마감
            item.get("bid_no", ""),             # S 공고번호
            item.get("bid_seq", ""),            # T 차수
            link,                               # U 링크
            item.get("collected_at", ""),       # V 수집시각
            item.get("unique_id", ""),          # W 고유ID
        ])

    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    return new_items
