"""
나라장터(G2B) 크롤러
- 사전규격공개 / 실공고 전체 수집 (페이지네이션)
- 키워드: 건설사업관리
- 수집 범위: 오늘 기준 2일 전 ~ 오늘 (KST)
"""
import requests
from datetime import datetime, timedelta, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import G2B_API_KEY

BASE_URL           = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService"
PRENOTICE_BASE_URL = "https://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService"
ORDERPLAN_BASE_URL = "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService"
KEYWORD  = "건설사업관리"
KST      = timezone(timedelta(hours=9))

# 사전규격/발주계획 공통 키워드 (클라이언트 필터용)
CM_KEYWORDS = [
    "건설사업관리", "건설사업 관리", "CM용역", "건설관리",
    "감독권한대행", "건설PM",
]


# ── 유틸 ───────────────────────────────────────────────────────

def _now_kst() -> datetime:
    return datetime.now(KST)


def _past(days: int = 2):
    """KST 기준 현재~N일 전 날짜 반환"""
    today = _now_kst()
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
    """날짜만 파싱 (YYYY-MM-DD)"""
    if not raw:
        return ""
    s = str(raw).strip()
    if not s or s in ("0", "null", "None"):
        return ""
    digits = s.replace("-", "").replace(":", "").replace(" ", "")
    if len(digits) >= 8 and digits[:8].isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return s


def _parse_datetime(raw) -> str:
    """날짜+시간 파싱 (YYYY-MM-DD HH:MM) — 공고일에 사용"""
    if not raw:
        return ""
    s = str(raw).strip()
    if not s or s in ("0", "null", "None"):
        return ""
    digits = s.replace("-", "").replace(":", "").replace(" ", "")
    if len(digits) >= 12 and digits[:12].isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]} {digits[8:10]}:{digits[10:12]}"
    if len(digits) >= 8 and digits[:8].isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return s


def _yn(val: str) -> str:
    if val == "Y": return "있음"
    if val == "N": return "없음"
    return val or ""


def _classify_by_no(bid_no: str) -> str:
    """
    공고번호 prefix로 공고종류 추정 (ntceKindNm 보조)
    R26BD → 사전규격공개
    R26DD → 발주계획
    R26BK → 등록공고(실공고)
    """
    upper = bid_no.upper()
    if "BD" in upper[1:5]:
        return "사전규격공개"
    if "DD" in upper[1:5]:
        return "발주계획"
    if "BK" in upper[1:5]:
        return "등록공고"
    return ""


# ── 전체 페이지 수집 ────────────────────────────────────────────

def _fetch_all(endpoint: str, extra_params: dict, base_url: str = None) -> list:
    url_base  = base_url or BASE_URL
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
            resp  = requests.get(f"{url_base}/{endpoint}", params=params, timeout=20)
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

def _build_item(item: dict, source: str = "실공고") -> dict:
    # 금액: 사전규격은 배정예산 우선 / 실공고는 추정가격 우선
    if source == "사전규격":
        amt = _parse_amount(item.get("asignBdgtAmt") or item.get("presmptPrce"))
    else:
        amt = _parse_amount(item.get("presmptPrce") or item.get("asignBdgtAmt"))
    bid_no  = item.get("bidNtceNo", "")
    bid_seq = item.get("bidNtceOrd", "00")

    # 공고종류: API 원본 우선, 없으면 공고번호 prefix로 추정
    ntce_kind = item.get("ntceKindNm", "").strip()
    if not ntce_kind:
        ntce_kind = _classify_by_no(bid_no)

    # 정정공고 표시
    title = item.get("bidNtceNm", "")
    if item.get("reNtceYn") == "Y" and bid_seq != "00":
        title = f"[정정 {int(bid_seq)}차] {title}"

    url = item.get("bidNtceDtlUrl") or item.get("bidNtceUrl") or ""

    return {
        "collected_at": _now_kst().strftime("%Y-%m-%d %H:%M"),  # KST
        "unique_id":    f"bid_{bid_no}_{bid_seq}",
        # 공고 분류
        "ntce_kind":    ntce_kind,
        "bid_no":       bid_no,
        "bid_seq":      bid_seq,
        "title":        title,
        # 금액
        "amount":       amt,
        "amount_str":   _fmt_amount(amt),
        # 기관
        "org":          item.get("ntceInsttNm", ""),
        "demand_org":   item.get("dminsttNm", ""),
        # 일정 (공고일은 시간 포함)
        "announce_dt":  _parse_datetime(item.get("bidNtceDt")),
        "open_dt":      _parse_date(item.get("opengDt")),
        # 링크
        "url":          url,
    }


# ── 수집 함수 ───────────────────────────────────────────────────

def _build_prenotice_item(item: dict) -> dict:
    """HrcspSsstndrdInfoService 응답 → 표준 item 구조 변환"""
    amt    = _parse_amount(item.get("asignBdgtAmt") or item.get("presmptPrce"))
    reg_no = item.get("bfSpecRgstNo", "")
    title  = item.get("prdctClsfcNoNm") or ""
    url    = (f"https://www.g2b.go.kr:8101/ep/bp/bpbids/retrieveBfSpecDtl.do"
              f"?bfSpecRgstNo={reg_no}&releaseYn=Y") if reg_no else ""

    return {
        "collected_at": _now_kst().strftime("%Y-%m-%d %H:%M"),
        "unique_id":    f"pre_{reg_no}",
        "ntce_kind":    "사전규격공개",
        "bid_no":       reg_no,
        "bid_seq":      "00",
        "title":        title,
        "amount":       amt,
        "amount_str":   _fmt_amount(amt),
        "org":          item.get("orderInsttNm", ""),
        "demand_org":   item.get("rlDminsttNm", ""),
        "announce_dt":  _parse_datetime(item.get("rgstDt")),
        "open_dt":      _parse_date(item.get("opninRgstClseDt")),
        "url":          url,
    }


def collect_prenotice() -> list:
    """
    사전규격공개 수집 (HrcspSsstndrdInfoService)
    - data.go.kr에서 '조달청_나라장터 사전규격정보서비스' 별도 신청 필요
    - API 키가 없으면 빈 리스트 반환
    - 용역 엔드포인트(getPublicPrcureThngInfoServc) 사용, 키워드는 클라이언트 필터
    """
    if not G2B_API_KEY:
        print("[사전규격] API 키 미설정 — 수집 생략")
        return []

    start, end = _past(3)
    raw = _fetch_all(
        "getPublicPrcureThngInfoServc",
        {
            "inqryDiv":   "1",
            "inqryBgnDt": start + "0000",
            "inqryEndDt": end   + "2359",
        },
        base_url=PRENOTICE_BASE_URL,
    )

    # API가 키워드 검색을 지원하지 않으므로 클라이언트에서 필터
    def _title_of(i):
        return (i.get("bidNtceNm") or i.get("prdctClsfcNoNm") or i.get("specNm") or "")

    matched = [i for i in raw if any(kw in _title_of(i) for kw in CM_KEYWORDS)]
    print(f"[사전규격] 전체 {len(raw)}건 중 키워드 매칭 {len(matched)}건")
    return [_build_prenotice_item(i) for i in matched]


def _build_orderplan_item(item: dict) -> dict:
    """OrderPlanSttusService 응답 → 표준 item 구조 변환"""
    amt     = _parse_amount(item.get("sumOrderAmt") or item.get("orderContrctAmt"))
    plan_no = item.get("orderPlanUntyNo", "")

    return {
        "collected_at": _now_kst().strftime("%Y-%m-%d %H:%M"),
        "unique_id":    f"plan_{plan_no}",
        "ntce_kind":    "발주계획",
        "bid_no":       plan_no,
        "bid_seq":      "00",
        "title":        item.get("bizNm", ""),
        "amount":       amt,
        "amount_str":   _fmt_amount(amt),
        "org":          item.get("orderInsttNm", ""),
        "demand_org":   item.get("totlmngInsttNm", ""),
        "announce_dt":  _parse_datetime(item.get("nticeDt")),
        "open_dt":      "",   # 발주계획은 월 단위(orderMnth)만 제공, 생략
        "url":          (f"https://www.g2b.go.kr:8101/ep/bp/bpbids/retrieveOdrPlnDtl.do"
                         f"?orderPlanUntyNo={plan_no}") if plan_no else "",
    }


def collect_order_plans() -> list:
    """
    발주계획 수집 (OrderPlanSttusService)
    - data.go.kr에서 '조달청_나라장터 발주계획현황서비스' 별도 신청 필요
    - 필수 파라미터: orderPlanYr + inqryDiv (날짜 범위 미지원)
    - 해당 연도 전체 수집 후 키워드·날짜 클라이언트 필터
    """
    if not G2B_API_KEY:
        print("[발주계획] API 키 미설정 — 수집 생략")
        return []

    year = _now_kst().strftime("%Y")
    raw  = _fetch_all(
        "getOrderPlanSttusListServc",
        {"orderPlanYr": year, "inqryDiv": "1"},
        base_url=ORDERPLAN_BASE_URL,
    )

    # 키워드 필터
    matched = [i for i in raw if any(kw in i.get("bizNm", "") for kw in CM_KEYWORDS)]

    # 날짜 필터: 수집 범위(3일) 내 등록건만
    cutoff = (_now_kst() - timedelta(days=3)).strftime("%Y-%m-%d")
    recent = [i for i in matched if (i.get("nticeDt") or "") >= cutoff]

    print(f"[발주계획] 전체 {len(raw)}건 → 키워드 {len(matched)}건 → 최근 3일 {len(recent)}건")
    return [_build_orderplan_item(i) for i in recent]


def collect_real_bids() -> list:
    """실공고(등록공고) 수집 — 등록일 기준 3일 (KST)"""
    start, end = _past(3)
    raw = _fetch_all("getBidPblancListInfoServc", {
        "inqryDiv":   "1",
        "inqryBgnDt": start + "0000",
        "inqryEndDt": end   + "2359",
        "bidNtceNm":  KEYWORD,
    })
    return [_build_item(i, source="실공고") for i in raw]


def collect_all() -> list:
    results = []
    results += collect_prenotice()    # 사전규격
    results += collect_order_plans()  # 발주계획
    results += collect_real_bids()    # 실공고

    # 배치 내 중복 제거 (unique_id 기준, 사전규격 우선)
    seen, deduped = set(), []
    for item in results:
        uid = item.get("unique_id", "")
        if uid and uid not in seen:
            seen.add(uid)
            deduped.append(item)
    return deduped
