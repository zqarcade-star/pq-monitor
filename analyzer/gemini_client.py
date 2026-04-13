"""
Gemini Flash API 분석 클라이언트
questions: list of {"team": str, "name": str, "question": str, "hint": str, "type": str}

모델 전략:
- 1순위: gemini-2.5-flash (20회/일, 정확도 높음)
- 2순위: gemini-2.0-flash (1,500회/일, 안정적 fallback)
- 503(과부하) / 429(한도 초과) 시 자동 전환
"""
from __future__ import annotations


MODELS = ["models/gemini-2.5-flash", "models/gemini-2.0-flash"]


def analyze(text: str, questions: list[dict], api_key: str, max_retries: int = 5) -> dict:
    """
    Returns: {항목명: 답변, ...}
    503/429 오류 시 다음 모델로 전환, 각 모델 3회 재시도 (지수 백오프)
    """
    import time
    from google import genai

    client = genai.Client(api_key=api_key)

    question_block = "\n".join(
        f"{i+1}. [{q['name']}] {q['question']}"
        + (f"\n   힌트: {q['hint']}" if q.get("hint") else "")
        for i, q in enumerate(questions)
    )

    prompt = f"""[역할]
너는 대한민국의 「건설기술 진흥법」 및 국토교통부·행정안전부의 건설엔지니어링 입찰 지침에 정통한 '공공입찰 분석 전문가'이자 '데이터 엔지니어'야.
제공된 공고문과 세부평가기준 텍스트를 분석하여 입찰 참여 여부를 결정짓는 핵심 데이터를 정형화된 형태로 추출해야 해.

[작업]
제시된 문서(공고문, 과업지시서, 세부평가기준 등)를 바탕으로 다음 작업을 수행하라:
1. 사업의 기본 정보(용역명, 용역비, 기간 등)를 정확히 추출할 것.
2. 배점표와 작성지침을 대조하여 실질적 평가 방식을 분류할 것.
3. 면접/발표 유무 및 제안서 작성 분량 등 전략적 판단 요소를 식별할 것.

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

    last_error = None

    for model in MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                raw = response.text.strip()

                results = {}
                for q in questions:
                    name = q["name"]
                    for line in raw.splitlines():
                        if f"[{name}]" in line:
                            answer = line.split(":", 1)[-1].strip()
                            results[name] = answer
                            break
                    else:
                        results[name] = "파싱실패"

                return results

            except Exception as e:
                last_error = e
                err = str(e)
                if "503" in err or "UNAVAILABLE" in err:
                    time.sleep(2 ** attempt)
                elif "429" in err or "RESOURCE_EXHAUSTED" in err:
                    break  # 이 모델 한도 초과 → 다음 모델로
                else:
                    raise

    raise Exception(f"Gemini 분석 실패 — 잠시 후 다시 시도하세요. ({last_error})")


def ask_followup(text: str, question: str, api_key: str) -> str:
    """
    분석된 문서에 대해 추가 질의 응답
    """
    import time
    from google import genai

    client = genai.Client(api_key=api_key)

    prompt = f"""[역할]
너는 대한민국의 「건설기술 진흥법」 및 국토교통부·행정안전부의 건설엔지니어링 입찰 지침에 정통한 '공공입찰 분석 전문가'야.

[엄격한 규칙 — 반드시 준수]
- 반드시 아래 제공된 문서 내용만을 근거로 답변하라.
- 문서에 없는 내용은 절대 추측하거나 외부 지식으로 보완하지 마라.
- 문서에서 확인할 수 없는 경우 반드시 "문서에서 확인되지 않습니다"라고 명시하라.
- 답변 시 근거가 되는 문서 내 문장을 인용하라.

[질문]
{question}

=== 문서 내용 ===
{text[:80000]}
"""

    last_error = None

    for model in MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                return response.text.strip()
            except Exception as e:
                last_error = e
                err = str(e)
                if "503" in err or "UNAVAILABLE" in err:
                    time.sleep(2 ** attempt)
                elif "429" in err or "RESOURCE_EXHAUSTED" in err:
                    break  # 다음 모델로
                else:
                    raise

    raise Exception(f"Gemini 질의 실패 — 잠시 후 다시 시도하세요. ({last_error})")
