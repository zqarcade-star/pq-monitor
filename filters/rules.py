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


def _is_relevant(item: dict) -> bool:
    title = item.get("title", "")
    return any(kw in title for kw in TITLE_KEYWORDS)


def _passes_amount(item: dict) -> bool:
    """
    금액이 0(미기재)이면 통과, 금액이 있으면 기준 이상만 통과.
    사전규격 단계에서는 금액이 없는 경우가 많아 포함 처리.
    """
    amt = item.get("amount", 0)
    return amt == 0 or amt >= AMOUNT_THRESHOLD


def filter_items(items: list) -> list:
    passed, fail_kw, fail_amt = [], [], []
    for i in items:
        if not _is_relevant(i):
            fail_kw.append(i)
        elif not _passes_amount(i):
            fail_amt.append(i)
        else:
            passed.append(i)

    # 디버그: 사전규격 항목 통과 현황
    pre_total  = sum(1 for i in items   if "BD" in i.get("bid_no","").upper()[1:5])
    pre_passed = sum(1 for i in passed  if "BD" in i.get("bid_no","").upper()[1:5])
    print(f"[필터] 사전규격(R26BD) 수집:{pre_total}건 → 통과:{pre_passed}건")
    print(f"[필터] 키워드 탈락:{len(fail_kw)}건 / 금액 탈락:{len(fail_amt)}건")
    if fail_kw:
        print(f"[필터] 키워드 탈락 샘플: {fail_kw[0].get('title','')} / bid_no={fail_kw[0].get('bid_no','')}")

    passed.sort(key=lambda x: x.get("announce_dt", "") or "")
    return passed
