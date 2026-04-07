"""
필터링 규칙
- 추정가격 15억 이상만 통과 (금액 미기재는 포함)
- 제목에 '건설사업관리' 포함 여부 재확인 (API 검색 결과 검증)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import AMOUNT_THRESHOLD

TITLE_KEYWORDS = [
    "건설사업관리", "건설사업 관리", "CM용역", "건설관리",
    "감독권한대행", "건설PM",
]

TYPE_ORDER = {"발주계획": 0, "사전규격": 1, "실공고": 2}


def _is_relevant(item: dict) -> bool:
    title = item.get("title", "")
    return any(kw in title for kw in TITLE_KEYWORDS)


def _passes_amount(item: dict) -> bool:
    """
    금액이 0(미기재)이면 통과, 금액이 있으면 기준 이상만 통과.
    사전규격/발주계획 단계에서는 금액이 없는 경우가 많아 포함 처리.
    """
    amt = item.get("amount", 0)
    return amt == 0 or amt >= AMOUNT_THRESHOLD


def filter_items(items: list) -> list:
    result = [i for i in items if _is_relevant(i) and _passes_amount(i)]
    result.sort(key=lambda x: (
        TYPE_ORDER.get(x.get("type", "실공고"), 9),
        x.get("announce_dt", "") or x.get("prenotice_dt", ""),
    ))
    return result
