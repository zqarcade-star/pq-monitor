"""
나라장터(G2B) 크롤러
- 사전규격공개 / 실공고 전체 수집 (페이지네이션)
- 키워드: 건설사업관리
- API 제공 필드 전체 수집
"""
import requests
from datetime import datetime, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import G2B_API_KEY

BASE_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService"
KEYWORD  = "건설사업관리"


# ── 유틸 ───────────────────────────────────────────────────────

def _past(days: int = 7):
    today = datetime.now()
    return (today - timedelta(days=days)).strftime("%Y%m%d"), today.strftime("%Y%m%d")

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

def _yn(val: str) -> str:
    if val == "Y": return "있음"
    if val == "N": return "없음"
    return val or ""


# ── 전체 페이지 수집 ────────────────────────────────────────────

def _fetch_all(endpoint: str, extra_params: dict) -> list:
    all_items = []
    page = 1
    while True:
        params = {
            "serviceKey": G2B_API_KEY,
            "type":       "json",
            "numOfRows":  100,
            "pageNo":     page,
        }
        params.update(extra_params)
        try:
            resp  = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=20)
            resp.raise_for_status()
            data  = resp.json()
            body  = data.get("response", {}).get("body", {})
            items = body.get("items", [])
            if isinstance(items, dict):
                items = [items]
            items = items or []
            all_items += items

            total = int(body.get("totalCount", 0))
            print(f"[G2B/{endpoint}] 페이지 {page}: {len(items)}건 (누계 {len(all_items)}/{total})")

            if len(all_items) >= total or len(items) < 100:
                break
            page += 1
        except Exception as e:
            print(f"[G2B/{endpoint}] 페이지 {page} 실패: {e}")
            break
    return all_items


# ── 항목 변환 ───────────────────────────────────────────────────

def _build_item(item: dict) -> dict:
    amt     = _parse_amount(item.get("presmptPrce") or item.get("asignBdgtAmt"))
    bid_no  = item.get("bidNtceNo", "")
    bid_seq = item.get("bidNtceOrd", "00")

    # 정정공고 표시
    title = item.get("bidNtceNm", "")
    if item.get("reNtceYn") == "Y" and bid_seq != "00":
        title = f"[정정 {int(bid_seq)}차] {title}"

    url = item.get("bidNtceDtlUrl") or item.get("bidNtceUrl") or ""

    return {
        "collected_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "unique_id":     f"bid_{bid_no}_{bid_seq}",
        # 공고 기본
        "ntce_kind":     item.get("ntceKindNm", ""),       # 공고종류 (나라장터 원본)
        "bid_no":        bid_no,
        "bid_seq":       bid_seq,
        "title":         title,
        # 금액·방법
        "amount":        amt,
        "amount_str":    _fmt_amount(amt),
        "sucsfbid_mthd": item.get("sucsfbidMthdNm", ""),   # 낙찰방법
        "bid_mthd":      item.get("bidMethdNm", ""),        # 입찰방법
        # 기관
        "org":           item.get("ntceInsttNm", ""),       # 공고기관
        "demand_org":    item.get("dminsttNm", ""),         # 수요기관
        # 평가 방식
        "pq_yn":         _yn(item.get("pqEvalYn", "")),     # PQ 여부
        "tp_eval_yn":    _yn(item.get("tpEvalYn", "")),     # 기술제안 여부
        "site_yn":       _yn(item.get("ntceDscrptYn", "")), # 현장설명 여부
        # 일정
        "announce_dt":   _parse_date(item.get("bidNtceDt")),            # 공고일
        "bid_begin_dt":  _parse_date(item.get("bidBeginDt")),           # 입찰시작
        "bid_close_dt":  _parse_date(item.get("bidClseDt")),            # 제안서마감
        "pq_rcpt_dt":    _parse_date(item.get("pqApplDocRcptDt")),      # PQ서류마감
        "tp_close_dt":   _parse_date(item.get("tpEvalApplClseDt")),     # 기술제안마감
        "site_dt":       _parse_date(item.get("dcmtgOprtnDt")),         # 현장설명일
        "open_dt":       _parse_date(item.get("opengDt")),              # 개찰일
        "arslt_rcpt_dt": _parse_date(item.get("arsltReqstdocRcptDt")), # 실적서류마감
        "url":           url,
    }


# ── 수집 함수 ───────────────────────────────────────────────────

def collect_prenotice() -> list:
    start, end = _past(7)
    raw = _fetch_all("getBidPblancListInfoServcPPSSrch", {
        "inqryDiv":   "1",
        "inqryBgnDt": start + "0000",
        "inqryEndDt": end   + "2359",
        "bidNtceNm":  KEYWORD,
    })
    return [_build_item(i) for i in raw]


def collect_real_bids() -> list:
    start, end = _past(7)
    raw = _fetch_all("getBidPblancListInfoServc", {
        "inqryDiv":   "1",
        "inqryBgnDt": start + "0000",
        "inqryEndDt": end   + "2359",
        "bidNtceNm":  KEYWORD,
    })
    return [_build_item(i) for i in raw]


def collect_all() -> list:
    results = []
    results += collect_prenotice()   # 사전규격 먼저
    results += collect_real_bids()   # 실공고 나중

    # 배치 내 중복 제거 (unique_id 기준, 사전규격 우선)
    seen, deduped = set(), []
    for item in results:
        uid = item.get("unique_id", "")
        if uid and uid not in seen:
            seen.add(uid)
            deduped.append(item)
    return deduped
