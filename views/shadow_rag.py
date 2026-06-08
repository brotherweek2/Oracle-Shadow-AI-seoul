"""
💊 SHADOW AI ▸ RAG 처방 (행정동 단위)
================================================================
전이예측(SHADOW AI)의 결과를 다시 받아서, 행정동 단위로 RAG 처방을 수행한다.

흐름:
  전이예측 결과(shadow_prescriptions.csv: 위험등급·전이확률·Avoidance)
    + 위험동인(shap_top3.csv: 행정동별 SHAP 1~3위)
      → 행정동의 Q유형 산출 (전이확률_정규화 × Avoidance 4분면)
        → 지식그래프 1홉 검색 (제도 ↔ 낙인요소 충돌)
          → 근거 기반 처방 생성

벡터 임베딩 없이, 그래프 엣지를 그대로 따라가는 정확한 매칭으로 '검색'을 수행한다.
"""
import os
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from kb.prescriptions import KB, Q_COLORS, RAG_EXAMPLES  # noqa: E402
from kb.graph import build_graph, retrieve as graph_retrieve  # noqa: E402

GRADE_COLOR = {"최고위험": "#e74c3c", "고위험": "#e67e22", "중위험": "#f1c40f", "저위험": "#2ecc71"}
FIT_COLOR = {"적합": "#27ae60", "부분 적합": "#e67e22", "주의 필요": "#c0392b"}
Q_LABEL = {"Q1": "Q1 · 최고위험형", "Q2": "Q2 · 정서취약형",
           "Q3": "Q3 · 상대안전형", "Q4": "Q4 · 자기해결형"}


@st.cache_resource
def get_graph():
    return build_graph()


@st.cache_data
def load_presc():
    p = ROOT / "Outputs" / "shadow_ai" / "shadow_prescriptions.csv"
    return pd.read_csv(p, encoding="utf-8-sig") if p.exists() else None


@st.cache_data
def load_shap_top3():
    p = ROOT / "Outputs" / "전이예측" / "shap_top3.csv"
    return pd.read_csv(p, encoding="utf-8-sig") if p.exists() else None


@st.cache_data
def quad_splits(deps, avos):
    """전이예측 결과 분포로 행정동 4분면 경계(중앙값)를 정한다."""
    return float(pd.Series(deps).median()), float(pd.Series(avos).median())


def quadrant_of(dep, avo, dep_split, avo_split):
    """전이확률_정규화(=Dependency축) × Avoidance 로 행정동 Q유형 산출."""
    dh, ah = dep >= dep_split, avo >= avo_split
    if dh and ah:
        return "Q1"
    if dh and not ah:
        return "Q2"
    if (not dh) and (not ah):
        return "Q3"
    return "Q4"


# ── 헤더 ──────────────────────────────────────────────────────────────
st.markdown(
    "<div class='hero'><h1>💊 RAG 처방 · 행정동 단위</h1>"
    "<p>전이예측(SHADOW AI) 결과와 SHAP 위험동인을 받아, 지식그래프 1홉 검색으로 "
    "행정동에 맞는 제도를 낙인-적합성까지 따져 처방합니다.</p></div>",
    unsafe_allow_html=True,
)

presc = load_presc()
shap3 = load_shap_top3()

if presc is None:
    st.error("전이예측 결과(Outputs/shadow_ai/shadow_prescriptions.csv)가 없어요. "
             "**전이예측** 페이지에서 분석을 먼저 실행해 주세요.")
    st.stop()

df = presc.dropna(subset=["전이확률_정규화", "Avoidance", "위험등급"]).copy()
dep_split, avo_split = quad_splits(df["전이확률_정규화"].tolist(), df["Avoidance"].tolist())

# ── 행정동 선택 ───────────────────────────────────────────────────────
c1, c2 = st.columns([1, 2])
with c1:
    gu = st.selectbox("자치구", sorted(df["자치구"].unique()), key="rag_gu")
with c2:
    sub = df[df["자치구"] == gu].sort_values("Shadow_Score", ascending=False)
    dong = st.selectbox("행정동  (전이위험 높은 순)", sub["행정동"].tolist(), key="rag_dong")

row = df[(df["자치구"] == gu) & (df["행정동"] == dong)].iloc[0]
dep_v = float(row["전이확률_정규화"])
avo_v = float(row["Avoidance"])
score = float(row["Shadow_Score"])
grade = str(row["위험등급"])
gcol = GRADE_COLOR.get(grade, "#95a5a6")
q_type = quadrant_of(dep_v, avo_v, dep_split, avo_split)
qcol = Q_COLORS.get(q_type, "#95a5a6")
kb = KB.get(q_type, {})

# ── 전이예측 요약 (RAG 입력) ──────────────────────────────────────────
st.markdown(
    f"## 📍 {gu} {dong} "
    f"<span class='chip' style='background:{gcol}'>{grade}</span> "
    f"<span class='chip' style='background:{qcol}'>{Q_LABEL.get(q_type, q_type)}</span>",
    unsafe_allow_html=True,
)
m1, m2, m3 = st.columns(3)
m1.metric("Shadow Score", f"{score:.1f}")
m2.metric("전이확률(Dependency축)", f"{dep_v:.1f}")
m3.metric("Avoidance(복지 회피)", f"{avo_v:.1f}")
st.markdown(
    f"<div class='note'>이 처방은 <b>전이예측 결과</b>(위험등급 {grade} · Shadow Score "
    f"{score:.1f})를 입력으로 받아, 행정동의 유형을 <b>{Q_LABEL.get(q_type, q_type)}</b>"
    f"으로 판정하고 그에 맞춰 생성됩니다.</div>",
    unsafe_allow_html=True,
)

# ── 위험동인 (SHAP) ───────────────────────────────────────────────────
drivers = []
if shap3 is not None:
    sr = shap3[(shap3["자치구"] == gu) & (shap3["행정동"] == dong)]
    if not sr.empty:
        s = sr.iloc[0]
        for i in (1, 2, 3):
            nm, val = s.get(f"{i}위원인"), s.get(f"{i}위SHAP")
            if pd.notna(nm):
                drivers.append((str(nm), float(val)))

if drivers:
    st.markdown("<div class='sec'>🔬 이 행정동이 위험한 이유 (SHAP 위험동인)</div>", unsafe_allow_html=True)
    dcols = st.columns(len(drivers))
    for col, (nm, val) in zip(dcols, drivers):
        col.markdown(
            f"<div class='card' style='text-align:center'>"
            f"<div style='font-size:.78rem;color:#7b8794'>위험 기여</div>"
            f"<div style='font-size:1.05rem;font-weight:800;color:#1f2d3d'>{nm}</div>"
            f"<div style='font-size:.9rem;color:#e74c3c;font-weight:700'>+{val:.3f}</div></div>",
            unsafe_allow_html=True,
        )
    st.caption("전이예측 모델(Gradient Boosting)이 이 행정동의 전이확률을 끌어올린 상위 요인입니다.")

st.divider()

# ── RAG 실행 ──────────────────────────────────────────────────────────
RETR_BADGE = ("<span style='background:#e8f8f0;color:#1e8449;padding:2px 10px;border-radius:10px;"
              "font-size:.78rem;font-weight:700'>✅ 그래프 검색 · 1홉 룩업</span> "
              "<span style='color:#999;font-size:.8rem'>— 임베딩·벡터DB 없이 "
              f"‘{q_type}’ 노드에서 [권장]→[자극] 엣지를 따라가 [민감]과 겹치는 충돌을 계산한 "
              "<b>실제 그래프 탐색 결과</b>입니다.</span>")
GEN_BADGE = ("<span style='background:#fff3cd;color:#856404;padding:2px 10px;border-radius:10px;"
             "font-size:.78rem;font-weight:700'>⚠️ LLM 생성 · 데모</span> "
             "<span style='color:#999;font-size:.8rem'>— 위 그래프 검색·충돌분석 + 전이예측 결과를 "
             "근거로 생성하는 자리. 지금은 결과와 일치하는 사전 작성 예시로 흐름을 시연합니다.</span>")

graph_result = graph_retrieve(get_graph(), q_type)


def show_retrieved(animate):
    st.markdown("### 🔎 1단계 · 검색 (Retrieve) — 그래프 1홉 룩업")
    st.markdown(RETR_BADGE, unsafe_allow_html=True)
    sens = graph_result["sensitive"]
    sens_text = (", ".join(f"`{s}`" for s in sens) if sens
                 else "해당 없음 — 회피축이 낮아 특별히 민감한 요소 없음")
    st.caption(f"🧭 탐색 경로: **{q_type}** →[민감]→ 낙인요소 = {sens_text}")
    for hit in graph_result["hits"]:
        fc = FIT_COLOR[hit["fit"]]
        with st.container(border=True):
            st.markdown(
                f"**{hit['name']}** · {hit['주최']} "
                f"<span class='chip' style='background:{fc};font-size:.72rem'>{hit['fit']}</span>",
                unsafe_allow_html=True,
            )
            st.caption(f"{hit['내용']} ({hit['시행']})")
            st.caption(f"📎 {hit['url']}")
            if hit["conflicts"]:
                st.markdown(
                    f"<span style='color:#c0392b;font-size:.8rem'>⚡ 충돌(민감 ∩ 자극): "
                    f"{' · '.join(hit['conflicts'])}</span>", unsafe_allow_html=True)
            if hit["side_effects"]:
                st.markdown(
                    f"<span style='color:#888;font-size:.8rem'>· 부수효과(자극하나 이 유형엔 비민감): "
                    f"{' · '.join(hit['side_effects'])}</span>", unsafe_allow_html=True)
        if animate:
            time.sleep(0.3)


driver_line = ""
if drivers:
    driver_line = "위험동인(SHAP): " + ", ".join(f"{n}(+{v:.2f})" for n, v in drivers) + ".\n\n"
example = RAG_EXAMPLES.get(q_type, "").format(gu=f"{gu} {dong}", dep=f"{dep_v:.1f}", avo=f"{avo_v:.1f}")
full_gen = (f"**[전이예측 입력]**  위험등급 **{grade}** · Shadow Score {score:.1f} · "
            f"유형 {Q_LABEL.get(q_type, q_type)}\n\n{driver_line}"
            f"**[처방 방향]**  {kb.get('처방방향', '')}\n\n---\n\n{example}")

done_key = f"rag_done_{gu}_{dong}"
pressed = st.button("▶ RAG 처방 생성 시작", type="primary", key=f"rag_btn_{gu}_{dong}")
if pressed:
    st.session_state[done_key] = True

if st.session_state.get(done_key):
    if pressed:
        with st.spinner("🔎 지식그래프에서 1홉 탐색 중..."):
            time.sleep(0.8)
        show_retrieved(animate=True)
        st.markdown("### 🧠 2단계 · 생성 (Generate)")
        st.markdown(GEN_BADGE, unsafe_allow_html=True)
        with st.spinner("🧠 전이예측 결과 + 그래프 검색으로 처방 생성 중..."):
            time.sleep(0.7)

        def streamer():
            for para in full_gen.split("\n\n"):
                yield para + "\n\n"
                time.sleep(0.35)
        with st.container(border=True):
            st.write_stream(streamer)
    else:
        show_retrieved(animate=False)
        st.markdown("### 🧠 2단계 · 생성 (Generate)")
        st.markdown(GEN_BADGE, unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(full_gen)
else:
    st.info("▶ 위 버튼을 누르면 **검색(Retrieve) → 생성(Generate)** 과정이 순서대로 시연됩니다.")

# ── 출처 · 한계 ───────────────────────────────────────────────────────
with st.expander("📎 출처 전체 · 한계 명시"):
    for i, inst in enumerate(kb.get("제도후보", []), 1):
        st.markdown(f"[출처{i}] {inst['name']} — {inst['url']}")
    st.caption("※ 본 처방은 전이예측(행정동 단위) 결과와 Q유형 심리기저에 근거한 정책 설계 적합성 평가이며, "
               "행정동 단위 신호입니다 (개인 단위 처방 아님).")

# ── (선택) 실제 LLM 연결 ──────────────────────────────────────────────
with st.expander("✨ 실제 LLM 연결 (Claude API · 데모 예시를 실시간 생성으로 대체)"):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.info("환경변수 `ANTHROPIC_API_KEY` 설정 시, 위 **전이예측 결과 + 그래프 검색·충돌분석**을 "
                "컨텍스트로 넘겨 Claude가 처방글을 **실시간 생성**합니다. 키 없이도 위 예시는 표시됩니다.")
    else:
        if st.button("처방문 실시간 생성", key=f"llm_{gu}_{dong}"):
            try:
                import anthropic
                client = anthropic.Anthropic()
                docs = "\n".join(
                    f"- {h['name']} ({h['주최']}) · 적합도: {h['fit']} "
                    f"· 충돌: {h['conflicts'] or '없음'} · 부수효과: {h['side_effects'] or '없음'}\n"
                    f"  내용: {h['내용']} (URL: {h['url']})"
                    for h in graph_result["hits"])
                prompt = (
                    "당신은 복지 정책 상담사다. 아래는 전이예측 결과와, 지식그래프를 1홉 탐색해 찾은 "
                    "제도 후보·낙인적합성 분석이다 — 이 정보만 근거로(밖의 사실 생성 금지) "
                    f"{gu} {dong}(위험등급 {grade}, Shadow Score {score:.1f}, 유형 {q_type}, "
                    f"Dependency {dep_v:.1f}, Avoidance {avo_v:.1f})에 대한 처방을 쓰라. "
                    f"{driver_line}그래프가 표시한 충돌·적합도를 그대로 반영하고, 마지막에 "
                    "'행정동 단위 신호'임을 명시하라.\n\n"
                    f"[처방방향] {kb.get('처방방향', '')}\n[그래프 검색·분석 결과]\n{docs}"
                )
                resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=900,
                                              messages=[{"role": "user", "content": prompt}])
                st.markdown(resp.content[0].text)
            except Exception as e:
                st.error(f"생성 실패: {e}")
