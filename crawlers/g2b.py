"""
나라장터(G2B) 크롤러
- 사전규격공개 / 실공고 수집
- 키워드: 건설사업관리
"""
import requests
from datetime import datetime, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import G2B_API_KEY

BASE_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService"
KEYWORD  = "건설사업관리"


# ── 날짜 범위 ──────────────────────────────────────────────────

def _past(days: int = 7):
    today = datetime.now()
    return (today - timedelta(days=days)).strftime("%Y%m%d"), today.strftime("%Y%m%d")


# ── 공통 유틸 ──────────────────────────────────────────────────

def _parse_amount(raw) -> int:
    if not raw:
        return 0
    try:
        return int(str(raw).replace(",", "").replace("원", "").strip())
    except ValueError:
        return 0

def _fmt_amount(amount: int) -> str:
    if not amount:
        return "-"
    if amount >= 1_0000_0000:
        return f"{amount / 1_0000_0000:.1f}억"
    if amount >= 10_000:
        return f"{amount / 10_000:.0f}만"
    return f"{amount:,}원"

def _parse_date(raw) -> str:
    """'2026-03-31 06:16:53' 또는 'YYYYMMDD...' → 'YYYY-MM-DD'"""
    if not raw:
        return ""
    s = str(raw).strip()
    if not s or s in ("0", "null", "None"):
        return ""
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s

def _map_bid_method(sucsfbid: str, bid: str) -> str:
    s = f"{sucsfbid} {bid}"
    if "협상" in s:
        return "협상(기술제안)"
    if "soq" in s.lower() or "자격사전심사" in s:
        return "SOQ"
    if "최저가" in s:
        return "최저가"
    if "적격" in s:
        return "적격심사"
    if "서면" in s:
        return "서면평가"
    return sucsfbid or bid or "-"

def _fetch(endpoint: str, extra_params: dict) -> list:
    params = {
        "serviceKey": G2B_API_KEY,
        "type":       "json",
        "numOfRows":  100,
        "pageNo":     1,
    }
    params.update(extra_params)
    try:
        resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=15)
        resp.raise_for_status()
        data  = resp.json()
        items = data.get("response", {}).get("body", {}).get("items", [])
        if isinstance(items, dict):
            items = [items]
        return items or []
    except Exception as e:
        print(f"[G2B/{endpoint}] 수집 실패: {e}")
        return []

def _build_item(item: dict, type_label: str) -> dict:
    """API 응답 항목을 공통 형식으로 변환"""
    amt     = _parse_amount(item.get("presmptPrce") or item.get("asignBdgtAmt"))
    bid_no  = item.get("bidNtceNo", "")
    bid_seq = item.get("bidNtceOrd", "00")

    # API가 직접 제공하는 URL 우선 사용
    url = (
        item.get("bidNtceDtlUrl") or
        item.get("bidNtceUrl") or
        ""
    )

    return {
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type":         type_label,
        "unique_id":    f"bid_{bid_no}",           # 두 API 간 중복 방지
        "bid_no":       bid_no,
        "title":        item.get("bidNtceNm", ""),
        "amount":       amt,
        "amount_str":   _fmt_amount(amt),
        "bid_method":   _map_bid_method(
                            item.get("sucsfbidMthdNm", ""),
                            item.get("bidMethdNm", "")  # ← 정확한 필드명
                        ),
        "org":          item.get("ntceInsttNm", ""),
        "demand_org":   item.get("dminsttNm", ""),
        "prenotice_dt": "",
        "announce_dt":  _parse_date(item.get("bidNtceDt")),
        "proposal_dt":  _parse_date(item.get("bidClseDt")),
        "open_dt":      _parse_date(item.get("opengDt")),
        "url":          url,
    }


# ── 사전규격 (먼저 수집 → 중복 시 사전규격 우선) ──────────────

def collect_prenotice() -> list:
    start, end = _past(7)
    raw = _fetch("getBidPblancListInfoServcPPSSrch", {
        "inqryDiv":   "1",
        "inqryBgnDt": start + "0000",
        "inqryEndDt": end   + "2359",
        "bidNtceNm":  KEYWORD,
    })
    return [_build_item(i, "사전규격") for i in raw]


# ── 실공고 ─────────────────────────────────────────────────────

def collect_real_bids() -> list:
    start, end = _past(7)
    raw = _fetch("getBidPblancListInfoServc", {
        "inqryDiv":   "1",
        "inqryBgnDt": start + "0000",
        "inqryEndDt": end   + "2359",
        "bidNtceNm":  KEYWORD,
    })

    # 정정공고 중복 제거: 같은 bidNtceNo 중 bidNtceOrd 가장 높은 것만 유지
    latest = {}
    for item in raw:
        no  = item.get("bidNtceNo", "")
        seq = item.get("bidNtceOrd", "00")
        if no not in latest or seq > latest[no].get("bidNtceOrd", "00"):
            latest[no] = item

    return [_build_item(i, "실공고") for i in latest.values()]


# ── 전체 수집 ──────────────────────────────────────────────────

def collect_all() -> list:
    # 사전규격 먼저 → 실공고 나중 (동일 공고번호 중복 시 사전규격 표시 우선)
    results = []
    results += collect_prenotice()
    results += collect_real_bids()
    return results
