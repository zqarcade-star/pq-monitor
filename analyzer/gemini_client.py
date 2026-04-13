"""
Gemini Flash API 분석 클라이언트
questions: list of {"team": str, "name": str, "question": str, "hint": str, "type": str}
"""


def analyze(text: str, questions: list[dict], api_key: str) -> dict:
    """
    Returns: {항목명: 답변, ...}
    """
    from google import genai

    client = genai.Client(api_key=api_key)

    question_block = "\n".join(
        f"{i+1}. [{q['name']}] {q['question']}"
        + (f"\n   힌트: {q['hint']}" if q.get("hint") else "")
        for i, q in enumerate(questions)
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
