"""
POC: HWP 텍스트 추출 + Gemini Flash 분석
실행: python poc.py
"""
import subprocess, sys, os, zipfile
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from pathlib import Path
from xml.etree import ElementTree as ET


# ── 설정 ────────────────────────────────────────────────────────
HWP_FILES = [
    "공고문_나노융합국가산업단지 내 국민체육센터, 밀양시 종합사회복지관 건립사업 통합건설사업관리용역.hwp",
    "과업지시서_나노융합국가산업단지 내 국민체육센터, 밀양시 종합사회복지관 건립사업 통합건설사업관리용역.hwp",
    "세부평가기준(나노융합국가산업단지 내 국민체육센터, 밀양시 종합사회복지관 건립사업 통합건설사업관리용역).hwp",
    "제안요청서(나노융합국가산업단지 내 국민체육센터, 밀양시 종합사회복지관 건립사업 통합건설사업관리용역).hwp",
]

# 제안팀 질문 목록 (POC용)
# 각 질문에 힌트(hint)를 붙여서 AI가 정확히 분류하도록 안내
QUESTIONS = [
    ("발표여부",
     """발표평가(PT)가 평가 항목으로 포함되어 있나요?
힌트: '발표', '면접', 'PT', '기술발표', '역량발표', '프레젠테이션' 등이
평가 방법이나 배점표에 언급되면 O, 없으면 X.
답변 형식: O 또는 X, 그리고 판단 근거 문장 1줄 인용."""),

    ("공고유형",
     """아래 기준으로 공고 유형을 분류하세요.
- 단순PQ: 사업수행능력평가서(PQ서류)만 제출, 발표/면접 없음
- 발표PQ: PQ서류 제출 + 발표 또는 면접 평가 포함
- 제안서포함: PQ서류 외에 별도 제안서(기술제안서, 사업수행계획서, 업무수행능력평가서 등) 추가 제출 필요
답변 형식: 단순PQ / 발표PQ / 제안서포함 중 하나."""),

    ("용역기간",
     """용역(사업) 수행 기간은 몇 개월인가요?
힌트: '공사기간', '용역기간', '사업기간' 항목을 찾으세요.
'착공일로부터 N개월' 또는 'N년 N개월' 형태로 표현될 수 있습니다.
답변 형식: 숫자(개월)만. 예) 24"""),

    ("별도제안서여부",
     """사업수행능력평가서(PQ서류) 외에 별도로 제출해야 하는 제안서가 있나요?

[PQ서류로 분류] 다음 서류는 PQ서류이므로 해당 없음:
- 사업수행능력평가서, 기술인보유현황, 실적확인서, 신용평가서

[제안서로 분류] 다음 서류가 있으면 O:
- 업무수행능력평가서, 건설사업관리 기술인 능력평가서
- 기술제안서, 사업수행계획서, 과업수행계획서
- 위와 유사한 별도 작성 제안 문서

답변 형식: O 또는 X, 그리고 해당 서류명 인용."""),

    ("제안서페이지수",
     """별도 제안서(업무수행능력평가서, 기술제안서 등)의 최대 페이지 수 제한이 있나요?
힌트: '페이지', '장', 'page', '분량' 관련 제한을 찾으세요.
답변 형식: 숫자 + 페이지. 예) 30페이지. 없으면 '제한없음'."""),

    ("제안서제출일",
     """제안서 또는 사업수행능력평가서 제출 마감일은?
힌트: '제출기한', '마감일', '접수기간 종료일'을 찾으세요.
답변 형식: YYYY.MM.DD. 없으면 '확인불가'."""),

    ("면접여부",
     """면접 평가가 평가 절차에 포함되어 있나요?
힌트: '면접', '대면평가', '현장평가', '구술평가' 등이 평가 항목에 있으면 O.
단순 서류심사만이면 X.
답변 형식: O 또는 X, 그리고 판단 근거 문장 1줄 인용."""),

    ("면접일자",
     """면접 예정 일자 또는 일정이 명시되어 있나요?
답변 형식: YYYY.MM.DD. 일정만 언급되고 날짜 미확정이면 '미정'. 면접 없으면 '해당없음'."""),
]

BASE_DIR = Path(__file__).parent


# ── HWP 텍스트 추출 ─────────────────────────────────────────────

def extract_hwp(path: Path) -> str:
    """HWP 파일 → 텍스트 (hwp5txt 사용)"""
    result = subprocess.run(
        ["hwp5txt", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        return f"[HWP 추출 실패: {result.stderr[:200]}]"
    return result.stdout.strip()


def extract_hwpx(path: Path) -> str:
    """HWPX 파일 → 텍스트 (ZIP 해제 + XML 파싱)"""
    texts = []
    try:
        with zipfile.ZipFile(path, "r") as z:
            for name in sorted(z.namelist()):
                if "section" in name.lower() and name.endswith(".xml"):
                    with z.open(name) as f:
                        try:
                            root = ET.parse(f).getroot()
                            chunk = " ".join(root.itertext()).strip()
                            if chunk:
                                texts.append(chunk)
                        except ET.ParseError:
                            pass
    except Exception as e:
        return f"[HWPX 추출 실패: {e}]"
    return "\n".join(texts)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".hwp":
        return extract_hwp(path)
    elif suffix == ".hwpx":
        return extract_hwpx(path)
    else:
        return f"[지원하지 않는 형식: {suffix}]"


# ── Gemini 분석 ─────────────────────────────────────────────────

def analyze_with_gemini(text: str, api_key: str) -> dict:
    from google import genai

    client = genai.Client(api_key=api_key)

    question_block = "\n".join(
        f"{i+1}. [{name}] {q}" for i, (name, q) in enumerate(QUESTIONS)
    )

    prompt = f"""당신은 한국 건설사업관리(CM) 입찰공고 문서 분석 전문가입니다.
아래 문서들은 하나의 공고에 포함된 첨부파일 전체입니다.

[배경 지식]
- 이 공고는 「건설기술진흥법」에 따른 건설사업관리 용역 입찰입니다.
- 입찰 참가자는 PQ서류(사업수행능력평가서)를 제출하며,
  일부 공고는 추가로 제안서(업무수행능력평가서, 기술인 능력평가서 등)를 요구합니다.
- 서류명이 공고마다 다를 수 있으므로, 명칭보다 내용과 역할로 판단하세요.

아래 질문들에 답하세요.
각 답변은 반드시 "[항목명]: 답변" 형식으로 작성하세요.
문서에서 확인 불가능한 경우에만 "확인불가"로 답하세요.

=== 질문 목록 ===
{question_block}

=== 문서 내용 ===
{text[:80000]}
"""

    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=prompt,
    )
    raw = response.text.strip()

    # 결과 파싱
    results = {}
    for name, _ in QUESTIONS:
        for line in raw.splitlines():
            if f"[{name}]" in line:
                answer = line.split(":", 1)[-1].strip()
                results[name] = answer
                break
        else:
            results[name] = "파싱실패"

    return results


# ── 메인 ────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("STEP 1: HWP 텍스트 추출 테스트")
    print("=" * 60)

    all_texts = {}
    for filename in HWP_FILES:
        path = BASE_DIR / filename
        if not path.exists():
            print(f"\n[건너뜀] 파일 없음: {filename}")
            continue

        print(f"\n▶ {filename[:40]}...")
        text = extract_text(path)
        all_texts[filename] = text

        if text.startswith("["):
            print(f"  결과: {text}")
        else:
            print(f"  추출 성공: {len(text):,}자")
            print(f"  미리보기: {text[:150].replace(chr(10), ' ')}...")

    if not all_texts:
        print("\n파일이 없습니다. HWP 파일을 pq_monitor 폴더에 넣어주세요.")
        return

    print("\n" + "=" * 60)
    print("STEP 2: Gemini Flash 분석 테스트")
    print("=" * 60)

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        api_key = input("\nGemini API 키를 입력하세요: ").strip()

    if not api_key:
        print("API 키 없음 — Gemini 분석 건너뜀")
        return

    # 전체 파일 텍스트 합치기 (공고 1건의 모든 첨부파일)
    combined = "\n\n".join(
        f"[파일: {Path(fn).name}]\n{txt}"
        for fn, txt in all_texts.items()
        if not txt.startswith("[")
    )

    print(f"\n총 {len(combined):,}자 → Gemini 전송 중...")

    try:
        results = analyze_with_gemini(combined, api_key)
    except Exception as e:
        print(f"Gemini 오류: {e}")
        # 사용 가능한 모델 목록 출력
        try:
            from google import genai as _genai
            _client = _genai.Client(api_key=api_key)
            print("\n사용 가능한 모델 목록:")
            for m in _client.models.list():
                if any(k in m.name.lower() for k in ["flash", "pro", "gemini"]):
                    print(f"  {m.name}")
        except Exception as e2:
            print(f"모델 목록 조회 실패: {e2}")
        return

    print("\n" + "=" * 60)
    print("분석 결과")
    print("=" * 60)
    for name, answer in results.items():
        print(f"  {name:<15}: {answer}")

    print("\nPOC 완료!")


if __name__ == "__main__":
    main()
