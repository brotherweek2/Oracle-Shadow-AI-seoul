"""
SHADOW 서비스 — 통합 셸 (진입점)
================================================
실행:  .venv\\Scripts\\python.exe -m streamlit run shadow_service.py

구성
  1. SHADOW Map
       └─ 🗺️ 진단 맵 (Dependency × Avoidance 4분면)   (views/shadow_map.py)
  2. SHADOW AI
       ├─ 🔮 전이예측      (shadow_dashboard.py — ★수정하지 않고 그대로 호출★)
       └─ 💊 RAG 처방      (views/shadow_rag.py — 전이예측 결과를 행정동 단위로 받아 처방)

원칙: shadow_dashboard.py 및 기존 산출물은 일절 수정하지 않는다.
      이 셸은 기존 코드를 '감싸서' 호출하고, Outputs/*.csv 를 읽어 화면을 구성한다.
"""
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="SHADOW 서비스",
    page_icon="🌃",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 전역 테마 (Map · RAG 페이지 공통 디자인) ──────────────────────────────
st.markdown("""
<style>
:root{
  --ink:#1f2d3d; --muted:#7b8794; --line:#e8edf3;
  --q1:#e74c3c; --q2:#e67e22; --q3:#3498db; --q4:#9b59b6;
  --accent:#5b6ee1;
}
.stApp{ background:#f6f8fb; }
section[data-testid="stSidebar"]{ background:#eef2f7; }
section[data-testid="stSidebar"] *{ font-family:'Malgun Gothic',sans-serif; }
.block-container{ padding-top:2.2rem; }

/* 헤더 */
.hero{
  background:linear-gradient(120deg,#2c3e63 0%,#5b6ee1 100%);
  border-radius:18px; padding:22px 26px; margin-bottom:18px;
  color:#fff; box-shadow:0 6px 22px rgba(58,77,161,.22);
}
.hero h1{ font-size:1.7rem; font-weight:800; margin:0 0 4px; color:#fff; }
.hero p{ margin:0; font-size:.92rem; opacity:.9; }

/* 섹션 제목 */
.sec{
  font-size:1.18rem; font-weight:800; color:var(--ink);
  border-left:5px solid var(--accent); padding-left:11px;
  margin:18px 0 12px;
}

/* 카드 */
.card{
  background:#fff; border-radius:14px; padding:16px 18px;
  box-shadow:0 2px 12px rgba(20,40,80,.06); border:1px solid var(--line);
}

/* 분면 설명 카드 */
.qcard{
  background:#fff; border-radius:14px; padding:14px 16px; height:100%;
  border:1px solid var(--line); border-top:5px solid #ccc;
  box-shadow:0 2px 10px rgba(20,40,80,.05);
}
.qcard .qname{ font-weight:800; font-size:1rem; }
.qcard .qstate{ font-size:.78rem; color:var(--muted); margin:2px 0 8px; }
.qcard .qrx{ font-size:.84rem; color:#34404e; line-height:1.55; }

/* 칩 */
.chip{ display:inline-block; padding:2px 11px; border-radius:12px;
  font-size:.76rem; font-weight:700; color:#fff; }

/* 인사이트 박스 */
.note{
  background:#eef3ff; border-left:4px solid var(--accent);
  border-radius:0 10px 10px 0; padding:11px 15px; margin:8px 0;
  font-size:.88rem; color:#34404e; line-height:1.65;
}
.note-warn{ background:#fff4f3; border-left-color:var(--q1); }
.note-ok{ background:#eefaf2; border-left-color:#27ae60; }
div[data-testid="stMetricValue"]{ font-weight:800; }
</style>
""", unsafe_allow_html=True)


# ── SHADOW AI · 전이예측: 업데이트된 shadow_dashboard.py 를 '수정 없이' 실행 ──
def shadow_ai_page():
    """업데이트된 shadow_dashboard.py 를 한 글자도 건드리지 않고 호출한다.

    - shadow_dashboard.py 가 부르는 st.set_page_config 는 통합 셸에서 이미 호출했으므로
      충돌한다. → 실행 중에만 잠깐 no-op 으로 무력화하고, 끝나면 원복.
    - __file__ 을 shadow_dashboard.py 경로로 주입해야 그 안의 `ROOT/Outputs` 데이터
      로딩 경로가 원래대로 작동한다.
    """
    import streamlit as _st
    _orig_cfg = _st.set_page_config
    _st.set_page_config = lambda *a, **k: None
    try:
        p = ROOT / "shadow_dashboard.py"
        code = compile(p.read_text(encoding="utf-8"), str(p), "exec")
        exec(code, {"__file__": str(p), "__name__": "__main__"})
    finally:
        _st.set_page_config = _orig_cfg


# ── 네비게이션 (2단 그룹) ────────────────────────────────────────────────
map_page   = st.Page("views/shadow_map.py", title="진단 맵 (4분면)", icon="🗺️", default=True)
ai_predict = st.Page(shadow_ai_page,        title="전이예측",        icon="🔮")
ai_rag     = st.Page("views/shadow_rag.py", title="RAG 처방",        icon="💊")

pg = st.navigation({
    "1. SHADOW Map": [map_page],
    "2. SHADOW AI":  [ai_predict, ai_rag],
})
pg.run()
