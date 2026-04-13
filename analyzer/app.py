"""
공고 첨부파일 AI 분석기 — Streamlit 앱
"""
import streamlit as st
import hashlib
import json
import pandas as pd

from extractor import extract_text
from gemini_client import analyze, ask_followup
import sheets_client

st.set_page_config(page_title="공고 분석기", page_icon="📋", layout="wide")

# ── 인증 ────────────────────────────────────────────────────────

def check_password() -> bool:
    """비밀번호 게이트. Streamlit Secrets의 PASSWORD 해시와 비교."""
    if st.session_state.get("authenticated"):
        return True

    st.title("📋 공고 첨부파일 AI 분석기")
    pwd = st.text_input("비밀번호", type="password", key="pwd_input")
    if st.button("로그인"):
        expected = st.secrets.get("PASSWORD_HASH", "")
        entered_hash = hashlib.sha256(pwd.encode()).hexdigest()
        if entered_hash == expected:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    return False


# ── Sheets 연결 (캐시) ──────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    creds_info = dict(st.secrets["gcp_service_account"])
    sheet_id = st.secrets["SHEET_ID"]
    return sheets_client.connect(creds_info, sheet_id)


# ── 페이지: 공고 분석 ────────────────────────────────────────────

def page_analyze():
    st.title("📋 공고 첨부파일 AI 분석")

    # 공고번호 입력
    bid_no = st.text_input(
        "공고번호 (선택)",
        placeholder="예) 20250300789-00",
        help="입력하면 분석 결과를 구글 시트 해당 행에 저장할 수 있습니다.",
    )

    # 팀 선택
    st.markdown("**분석할 팀 선택**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        team_common = st.checkbox("공통", value=True)
    with col2:
        team_plan = st.checkbox("기획팀")
    with col3:
        team_pq = st.checkbox("PQ팀")
    with col4:
        team_proposal = st.checkbox("제안팀")

    selected_teams = []
    if team_common:
        selected_teams.append("공통")
    if team_plan:
        selected_teams.append("기획팀")
    if team_pq:
        selected_teams.append("PQ팀")
    if team_proposal:
        selected_teams.append("제안팀")

    # 파일 업로드
    uploaded_files = st.file_uploader(
        "첨부파일 업로드 (다중 선택 가능)",
        type=["hwp", "hwpx", "pdf", "xlsx", "xls"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("첨부파일을 업로드하세요.")
        return

    if not selected_teams:
        st.warning("팀을 하나 이상 선택하세요.")
        return

    # 분석 시작
    if st.button("분석 시작", type="primary"):
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            st.error("GEMINI_API_KEY가 설정되지 않았습니다.")
            return

        # 텍스트 추출
        with st.spinner("파일에서 텍스트 추출 중..."):
            extracted = {}
            for f in uploaded_files:
                text = extract_text(f.read(), f.name)
                extracted[f.name] = text

        # 추출 결과 표시
        with st.expander("파일 추출 결과", expanded=False):
            for fname, text in extracted.items():
                if text.startswith("["):
                    st.error(f"**{fname}**: {text}")
                else:
                    st.success(f"**{fname}**: {len(text):,}자 추출")

        # 분석 가능한 텍스트만 합치기
        valid_texts = {
            fn: txt for fn, txt in extracted.items()
            if not txt.startswith("[")
        }
        if not valid_texts:
            st.error("분석 가능한 파일이 없습니다.")
            return

        combined = "\n\n".join(
            f"[파일: {fn}]\n{txt}" for fn, txt in valid_texts.items()
        )

        # Sheets에서 질문 로드
        with st.spinner("질문 설정 불러오는 중..."):
            try:
                spreadsheet = get_spreadsheet()
                questions = sheets_client.load_questions(spreadsheet, selected_teams)
            except Exception as e:
                st.error(f"Google Sheets 연결 실패: {e}")
                return

        if not questions:
            st.warning("선택한 팀에 해당하는 질문이 없습니다. 설정 탭에서 질문을 추가하세요.")
            return

        # Gemini 분석
        with st.spinner(f"Gemini AI 분석 중... ({len(combined):,}자)"):
            try:
                results = analyze(combined, questions, api_key)
            except Exception as e:
                st.error(f"Gemini 분석 실패: {e}")
                return

        # 결과 표시
        st.success("분석 완료!")
        st.subheader("분석 결과")

        result_df = pd.DataFrame([
            {
                "팀": next((q["team"] for q in questions if q["name"] == name), ""),
                "항목": name,
                "답변": answer,
            }
            for name, answer in results.items()
        ])
        st.dataframe(result_df, use_container_width=True, hide_index=True)

        # 세션에 결과 저장
        st.session_state["last_results"] = results
        st.session_state["last_bid_no"] = bid_no
        st.session_state["last_teams"] = selected_teams
        st.session_state["last_combined"] = combined

    # 시트 저장 버튼
    if st.session_state.get("last_results"):
        st.divider()
        saved_bid_no = st.session_state.get("last_bid_no", "")
        if saved_bid_no:
            if st.button("구글 시트에 저장", type="secondary"):
                with st.spinner("저장 중..."):
                    try:
                        spreadsheet = get_spreadsheet()
                        found = sheets_client.save_results(
                            spreadsheet,
                            saved_bid_no,
                            st.session_state["last_teams"],
                            st.session_state["last_results"],
                        )
                        if found:
                            st.success(f"공고번호 {saved_bid_no} 행에 저장 완료!")
                        else:
                            st.error(f"공고번호 '{saved_bid_no}'를 시트에서 찾을 수 없습니다.")
                    except Exception as e:
                        st.error(f"저장 실패: {e}")
        else:
            st.info("공고번호를 입력해야 시트에 저장할 수 있습니다.")

    # 추가 질의
    if st.session_state.get("last_combined"):
        st.divider()
        st.subheader("추가 질의")
        followup_q = st.text_area(
            "문서에 대해 추가로 궁금한 점을 입력하세요",
            placeholder="예) 입찰 참가 자격 요건은?\n예) 하도급 제한 조건이 있나요?",
            height=100,
        )
        if st.button("질의하기"):
            if not followup_q.strip():
                st.warning("질문을 입력하세요.")
            else:
                api_key = st.secrets.get("GEMINI_API_KEY", "")
                with st.spinner("Gemini AI 답변 생성 중..."):
                    try:
                        answer = ask_followup(
                            st.session_state["last_combined"],
                            followup_q,
                            api_key,
                        )
                        st.markdown("**답변:**")
                        st.markdown(answer)
                    except Exception as e:
                        st.error(f"질의 실패: {e}")


# ── 페이지: 질문 설정 ────────────────────────────────────────────

def page_settings():
    st.title("⚙️ 질문 설정")
    st.markdown("팀별 AI 질문을 관리합니다. 수정 후 **저장** 버튼을 누르세요.")

    with st.spinner("설정 불러오는 중..."):
        try:
            spreadsheet = get_spreadsheet()
            ws = sheets_client.get_or_create_settings_sheet(spreadsheet)
            rows = ws.get_all_records()
        except Exception as e:
            st.error(f"Google Sheets 연결 실패: {e}")
            return

    if not rows:
        st.info("질문이 없습니다.")
        return

    df = pd.DataFrame(rows, columns=sheets_client.SETTINGS_HEADERS)

    edited = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "팀": st.column_config.SelectboxColumn(
                "팀",
                options=["공통", "기획팀", "PQ팀", "제안팀"],
                required=True,
            ),
            "유형": st.column_config.SelectboxColumn(
                "유형",
                options=["O/X", "선택", "텍스트"],
                required=True,
            ),
            "AI질문": st.column_config.TextColumn("AI질문", width="large"),
            "힌트": st.column_config.TextColumn("힌트", width="large"),
        },
        hide_index=True,
    )

    if st.button("저장", type="primary"):
        with st.spinner("저장 중..."):
            try:
                updated = edited.values.tolist()
                sheets_client.save_questions(spreadsheet, updated)
                st.success("저장 완료!")
                st.cache_resource.clear()
            except Exception as e:
                st.error(f"저장 실패: {e}")


# ── 메인 ────────────────────────────────────────────────────────

def main():
    if not check_password():
        return

    page = st.sidebar.radio(
        "메뉴",
        ["공고 분석", "질문 설정"],
        label_visibility="collapsed",
    )

    if page == "공고 분석":
        page_analyze()
    else:
        page_settings()


if __name__ == "__main__":
    main()
