"""
Google Sheets 연동
- 설정 탭: 질문 목록 읽기
- 데이터 탭(sheet1): 공고번호(D열)로 행 찾아 M열~에 분석 결과 기록
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
KST = timezone(timedelta(hours=9))

# 설정 탭 이름 및 열 구조
SETTINGS_SHEET_NAME = "설정"
SETTINGS_HEADERS = ["팀", "항목명", "AI질문", "힌트", "유형"]

# 데이터 탭: 분석 결과 시작 열 (M = 13번째)
RESULT_START_COL = 13   # M열 (1-indexed)
BID_NO_COL = 4          # D열 (공고번호)

# 분석 결과 열 레이아웃 (M부터)
# M: 분석일시, N: 팀, O~: 항목별 결과 (질문 순서대로)
FIXED_RESULT_COLS = ["분석일시", "분석팀"]


# ── 초기 질문 데이터 (seed) ──────────────────────────────────────
SEED_QUESTIONS = [
    ("공통", "발표여부",
     "발표평가(PT)가 평가 항목으로 포함되어 있나요?",
     "'발표', '면접', 'PT', '기술발표', '역량발표', '프레젠테이션' 등이 평가 방법이나 배점표에 언급되면 O, 없으면 X.\n답변 형식: O 또는 X, 그리고 판단 근거 문장 1줄 인용.",
     "O/X"),
    ("공통", "공고유형",
     "아래 기준으로 공고 유형을 분류하세요.\n- 단순PQ: 사업수행능력평가서(PQ서류)만 제출, 발표/면접 없음\n- 발표PQ: PQ서류 제출 + 발표 또는 면접 평가 포함\n- 제안서포함: PQ서류 외에 별도 제안서(기술제안서, 사업수행계획서, 업무수행능력평가서 등) 추가 제출 필요",
     "",
     "선택"),
    ("제안팀", "용역기간",
     "용역(사업) 수행 기간은 몇 개월인가요?",
     "'공사기간', '용역기간', '사업기간' 항목을 찾으세요. '착공일로부터 N개월' 또는 'N년 N개월' 형태로 표현될 수 있습니다.\n답변 형식: 숫자(개월)만. 예) 24",
     "텍스트"),
    ("제안팀", "별도제안서여부",
     "사업수행능력평가서(PQ서류) 외에 별도로 제출해야 하는 제안서가 있나요?\n[PQ서류로 분류] 사업수행능력평가서, 기술인보유현황, 실적확인서, 신용평가서\n[제안서로 분류] 업무수행능력평가서, 건설사업관리 기술인 능력평가서, 기술제안서, 사업수행계획서, 과업수행계획서",
     "답변 형식: O 또는 X, 그리고 해당 서류명 인용.",
     "O/X"),
    ("제안팀", "제안서페이지수",
     "별도 제안서(업무수행능력평가서, 기술제안서 등)의 최대 페이지 수 제한이 있나요?",
     "'페이지', '장', 'page', '분량' 관련 제한을 찾으세요.\n답변 형식: 숫자 + 페이지. 예) 30페이지. 없으면 '제한없음'.",
     "텍스트"),
    ("제안팀", "제안서제출일",
     "제안서 또는 사업수행능력평가서 제출 마감일은?",
     "'제출기한', '마감일', '접수기간 종료일'을 찾으세요.\n답변 형식: YYYY.MM.DD. 없으면 '확인불가'.",
     "텍스트"),
    ("제안팀", "면접여부",
     "면접 평가가 평가 절차에 포함되어 있나요?",
     "'면접', '대면평가', '현장평가', '구술평가' 등이 평가 항목에 있으면 O. 단순 서류심사만이면 X.\n답변 형식: O 또는 X, 그리고 판단 근거 문장 1줄 인용.",
     "O/X"),
    ("제안팀", "면접일자",
     "면접 예정 일자 또는 일정이 명시되어 있나요?",
     "답변 형식: YYYY.MM.DD. 일정만 언급되고 날짜 미확정이면 '미정'. 면접 없으면 '해당없음'.",
     "텍스트"),
]


def connect(credentials_info: dict, sheet_id: str):
    """서비스 계정 JSON dict로 연결 (Streamlit Secrets 호환)"""
    creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id)


def get_or_create_settings_sheet(spreadsheet):
    """설정 탭이 없으면 생성하고 seed 데이터 삽입"""
    try:
        ws = spreadsheet.worksheet(SETTINGS_SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=SETTINGS_SHEET_NAME, rows=100, cols=10
        )
        # 헤더 삽입
        ws.append_row(SETTINGS_HEADERS)
        # Seed 질문 삽입
        rows = [[팀, 항목명, 질문, 힌트, 유형] for 팀, 항목명, 질문, 힌트, 유형 in SEED_QUESTIONS]
        ws.append_rows(rows)
        # 헤더 스타일
        ws.format("A1:E1", {
            "backgroundColor": {"red": 0.086, "green": 0.133, "blue": 0.243},
            "textFormat": {
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                "bold": True,
            },
            "horizontalAlignment": "CENTER",
        })
    return ws


def load_questions(spreadsheet, teams: list[str]) -> list[dict]:
    """
    설정 탭에서 선택된 팀의 질문 로드
    Returns: [{"team", "name", "question", "hint", "type"}, ...]
    """
    ws = get_or_create_settings_sheet(spreadsheet)
    rows = ws.get_all_records()
    return [
        {
            "team": r.get("팀", ""),
            "name": r.get("항목명", ""),
            "question": r.get("AI질문", ""),
            "hint": r.get("힌트", ""),
            "type": r.get("유형", ""),
        }
        for r in rows
        if r.get("팀") in teams and r.get("항목명")
    ]


def save_results(spreadsheet, bid_no: str, teams: list[str], results: dict) -> bool:
    """
    공고번호(D열)로 해당 행 찾아 M열부터 분석 결과 기록.
    Returns True if row found, False if not found.
    """
    sheet1 = spreadsheet.sheet1
    d_col_values = sheet1.col_values(BID_NO_COL)  # D열 전체

    row_idx = None
    for i, val in enumerate(d_col_values):
        if val == bid_no:
            row_idx = i + 1  # gspread 1-indexed
            break

    if row_idx is None:
        return False

    # 현재 M열 이후 헤더 확인 (1행)
    header_row = sheet1.row_values(1)
    # M열 이후 헤더 (0-indexed: RESULT_START_COL-1 이후)
    result_headers = header_row[RESULT_START_COL - 1:]

    # 써야 할 컬럼 목록: 분석일시, 분석팀, 항목들
    item_names = list(results.keys())
    desired_headers = FIXED_RESULT_COLS + item_names

    # 헤더에 없는 컬럼 추가
    for col_name in desired_headers:
        if col_name not in result_headers:
            result_headers.append(col_name)

    # 1행 헤더 업데이트
    col_count = len(header_row[:RESULT_START_COL - 1]) + len(result_headers)
    new_header = header_row[:RESULT_START_COL - 1] + result_headers
    sheet1.update("A1", [new_header])

    # 데이터 행 업데이트
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    team_str = ", ".join(teams)

    values_to_write = {}
    values_to_write["분석일시"] = now_kst
    values_to_write["분석팀"] = team_str
    for name, answer in results.items():
        values_to_write[name] = answer

    # result_headers 순서대로 값 배열 구성
    row_values = [values_to_write.get(h, "") for h in result_headers]

    # M열 위치부터 업데이트
    start_cell = gspread.utils.rowcol_to_a1(row_idx, RESULT_START_COL)
    end_cell = gspread.utils.rowcol_to_a1(row_idx, RESULT_START_COL + len(row_values) - 1)
    sheet1.update(f"{start_cell}:{end_cell}", [row_values])

    return True


def save_questions(spreadsheet, updated_rows: list[list]) -> None:
    """설정 탭 전체 데이터 업데이트 (헤더 제외)"""
    ws = get_or_create_settings_sheet(spreadsheet)
    ws.clear()
    ws.append_row(SETTINGS_HEADERS)
    if updated_rows:
        ws.append_rows(updated_rows)
