"""
나라장터(G2B) 크롤러
- 사전규격공개 / 실공고 수집
- 키워드: 건설사업관리
"""
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
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
    """다양한 날짜 형식을 YYYY-MM-DD로 통일"""
    if not raw:
        return ""
    s = str(raw).strip()
    if not s or s in ("0", "null", "None"):
        return ""
    # YYYY-MM-DD 또는 YYYY-MM-DD HH:MM 형식
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    # YYYYMMDD 또는 YYYYMMDDHHMMSS 형식
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

def _make_url(bid_no: str, bid_seq: str = "00") -> str:
    """나라장터 공고 상세 URL"""
    inner = f"/pt/menu/frameBidPbancDtl.do?bidno={bid_no}&bidseq={bid_seq}"
    return "https://www.g2b.go.kr/pt/menu/selectSubFrame.do?framesrc=" + quote(inner)

def _make_prenotice_url(reg_no: str) -> str:
    inner = f"/pt/menu/frameBfSpecRgsDtl.do?bfSpecRgsNo={reg_no}"
    return "https://www.g2b.go.kr/pt/menu/selectSubFrame.do?framesrc=" + quote(inner)

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


# ── 실공고 ─────────────────────────────────────────────────────

def collect_real_bids() -> list:
    start, end = _past(7)
    raw = _fetch("getBidPblancListInfoServc", {
        "inqryDiv":   "1",
        "inqryBgnDt": start + "0000",
        "inqryEndDt": end   + "2359",
        "bidNtceNm":  KEYWORD,
    })

    # ── 디버그: 첫 번째 항목 필드 확인 ──────────────────────────
    if raw:
        s = raw[0]
        print("[DEBUG 실공고 첫번째 항목]")
        print(f"  전체 필드: {list(s.keys())}")
        print(f"  bidNtceNo  : {s.get('bidNtceNo','없음')}")
        print(f"  bidNtceDt  : {s.get('bidNtceDt','없음')}")
        print(f"  bidClseDt  : {s.get('bidClseDt','없음')}")
        print(f"  opengDt    : {s.get('opengDt','없음')}")
        print(f"  ntceInsttNm: {s.get('ntceInsttNm','없음')}")
        print(f"  dminsttNm  : {s.get('dminsttNm','없음')}")
        print(f"  presmptPrce: {s.get('presmptPrce','없음')}")
    # ─────────────────────────────────────────────────────────────

    # 정정공고 중복 제거: 같은 bidNtceNo 중 bidNtceOrd 가장 높은 것만 유지
    latest = {}
    for item in raw:
        no  = item.get("bidNtceNo", "")
        seq = item.get("bidNtceOrd", "00")
        if no not in latest or seq > latest[no].get("bidNtceOrd", "00"):
            latest[no] = item
    raw = list(latest.values())

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    results = []
    for item in raw:
        amt     = _parse_amount(item.get("presmptPrce") or item.get("asignBdgtAmt"))
        bid_no  = item.get("bidNtceNo", "")
        bid_seq = item.get("bidNtceOrd", "00")
        results.append({
            "collected_at": now,
            "type":         "실공고",
            "unique_id":    f"공고_{bid_no}",
            "bid_no":       bid_no,
            "title":        item.get("bidNtceNm", ""),
            "amount":       amt,
            "amount_str":   _fmt_amount(amt),
            "bid_method":   _map_bid_method(
                                item.get("sucsfbidMthdNm", ""),
                                item.get("bidMthdNm", "")
                            ),
            "org":          item.get("ntceInsttNm", ""),
            "demand_org":   item.get("dminsttNm", ""),
            "prenotice_dt": "",
            "announce_dt":  _parse_date(item.get("bidNtceDt")),
            "proposal_dt":  _parse_date(item.get("bidClseDt")),
            "open_dt":      _parse_date(item.get("opengDt")),
            "url":          _make_url(bid_no, bid_seq),
        })
    return results


# ── 사전규격공개 ───────────────────────────────────────────────

def collect_prenotice() -> list:
    start, end = _past(7)
    raw = _fetch("getBidPblancListInfoServcPPSSrch", {
        "inqryDiv":   "1",
        "inqryBgnDt": start + "0000",
        "inqryEndDt": end   + "2359",
        "bidNtceNm":  KEYWORD,
    })

    # ── 디버그: 첫 번째 항목 필드 확인 ──────────────────────────
    if raw:
        s = raw[0]
        print("[DEBUG 사전규격 첫번째 항목]")
        print(f"  전체 필드: {list(s.keys())}")
        print(f"  bfSpecRgsNo     : {s.get('bfSpecRgsNo','없음')}")
        print(f"  bfSpecRgsDt     : {s.get('bfSpecRgsDt','없음')}")
        print(f"  opninRcptDdlnDt : {s.get('opninRcptDdlnDt','없음')}")
        print(f"  ntceInsttNm     : {s.get('ntceInsttNm','없음')}")
        print(f"  presmptPrce     : {s.get('presmptPrce','없음')}")
    # ─────────────────────────────────────────────────────────────

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    results = []
    for item in raw:
        amt    = _parse_amount(item.get("presmptPrce"))
        reg_no = item.get("bfSpecRgsNo", "")
        results.append({
            "collected_at": now,
            "type":         "사전규격",
            "unique_id":    f"규격_{reg_no}",
            "bid_no":       reg_no,
            "title":        item.get("bidNtceNm", "") or item.get("bfSpecRgsBzNm", ""),
            "amount":       amt,
            "amount_str":   _fmt_amount(amt),
            "bid_method":   "-",
            "org":          item.get("ntceInsttNm", ""),
            "demand_org":   item.get("dminsttNm", ""),
            "prenotice_dt": _parse_date(item.get("bfSpecRgsDt")),
            "announce_dt":  "",
            "proposal_dt":  _parse_date(item.get("opninRcptDdlnDt")),
            "open_dt":      "",
            "url":          _make_prenotice_url(reg_no),
        })
    return results


# ── 전체 수집 ──────────────────────────────────────────────────

def collect_all() -> list:
    results = []
    results += collect_real_bids()
    results += collect_prenotice()
    return results
