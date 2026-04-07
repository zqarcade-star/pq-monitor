# ================================================================
# crawlers/d2b.py  —  국방전자조달 크롤러
# ================================================================
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "https://www.d2b.go.kr"
HEADERS  = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.d2b.go.kr",
}
TIMEOUT  = 20

SEARCH_TARGETS = [
    ("건설사업", "국방_CM"),
    ("설계",     "국방_설계"),
]


def _fetch_list(session, keyword: str, category: str) -> list:
    today = datetime.now().strftime("%Y%m%d")
    params = {
        "key":           "32",
        "bidNm":         keyword,
        "fromDate":      today,
        "toDate":        today,
        "pageIndex":     "1",
    }
    try:
        resp = session.get(
            f"{BASE_URL}/psb/bid/serviceBidAnnounceList.do",
            params=params,
            timeout=TIMEOUT
        )
        resp.raise_for_status()
        resp.encoding = "UTF-8"
    except Exception as e:
        print(f"[D2B] '{keyword}' 요청 실패: {e}")
        return []

    soup  = BeautifulSoup(resp.text, "lxml")
    rows  = (
        soup.select("table tbody tr") or
        soup.select(".list_wrap tbody tr") or
        soup.select("tr")
    )
    items = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    for row in rows:
        cols = row.select("td")
        if len(cols) < 3:
            continue
        try:
            title_tag = row.select_one("a[href]")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title:
                continue
            bid_no = cols[0].get_text(strip=True).replace(" ", "")
            href   = title_tag.get("href", "")
            if href and not href.startswith("http"):
                href = BASE_URL + href
            announce_dt = cols[2].get_text(strip=True)[:10] if len(cols) > 2 else today_str
            deadline_dt = cols[3].get_text(strip=True)[:10] if len(cols) > 3 else ""
            items.append({
                "id":          f"D2B_{bid_no}",
                "source":      "국방전자조달",
                "type":        "공고",
                "category":    category,
                "title":       title,
                "org":         "국방부",
                "amount":      0,
                "announce_dt": announce_dt,
                "deadline_dt": deadline_dt,
                "url":         href or f"{BASE_URL}/psb/bid/serviceBidAnnounceList.do?key=32",
            })
        except Exception:
            continue
    return items


def collect_all() -> list:
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(BASE_URL, timeout=TIMEOUT)
    except Exception:
        pass

    results = []
    for keyword, category in SEARCH_TARGETS:
        items = _fetch_list(session, keyword, category)
        print(f"[D2B] '{keyword}' → {len(items)}건")
        results += items
    return results