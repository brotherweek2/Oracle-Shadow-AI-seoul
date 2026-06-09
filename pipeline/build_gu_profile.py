# -*- coding: utf-8 -*-
"""
gu_profile.json 빌더
====================
3개 인덱스 CSV  →  자치구 → 행정동 중첩 JSON. (원본값 그대로, 반올림 없음)

  진단(자치구) = shadow_index(Q·Dependency·Avoidance 등) + avoidance_index(회피 4요소)
  행정동 골격  = dependency_index(현재 Dependency)

전이예측 필드(전이확률·위험등급·shap) + 회피 기여도(가중편차·절대가중)는 None으로 비워둠.
→ 팀원이 채우면 완성.

실행:  python build_gu_profile.py
출력:  data/gu_profile.json
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent   # pipeline/ → 레포 루트
OUT_DIR = ROOT / "Data"
OUT_DIR.mkdir(exist_ok=True)

# ── 1. 인덱스 3개 읽기 ──────────────────────────────────────────────
shadow = pd.read_csv(ROOT / "Outputs" / "shadow_index.csv", encoding="utf-8-sig")
avo = pd.read_csv(ROOT / "Outputs" / "복지의 역설" / "avoidance_index.csv", encoding="utf-8-sig")
dep = pd.read_csv(ROOT / "Outputs" / "편의의 역설" / "dependency_index.csv",
                  encoding="utf-8-sig", dtype={"행정동코드": str})

# ── 2. 회피 4요소 원본 lookup (자치구 → {요소: 원본값}) ────────────
COMP = {"A_도움부재": "도움부재", "B_외로움부정": "외로움부정",
        "C_복지불신": "복지불신", "D_네트워크축소": "네트워크축소"}
COMP_KEYS = list(COMP.values())
avo_map = {
    row["자치구"]: {clean: float(row[col]) for col, clean in COMP.items()}
    for _, row in avo.iterrows()
}
# avoidance_index 부가 컬럼 (자치구코드·Avoidance_3var)
avo_extra = {
    row["자치구"]: {
        "자치구코드": int(row["자치구코드"]),
        "avoidance_3var": float(row["Avoidance_3var"]),
    }
    for _, row in avo.iterrows()
}

# ── 2b. 편의의존 5요소 → 자치구 집계 (Q 만든 방식 = 행정동 단순평균) ────
#   원본 구성요소만 (기여도 분해 X — 편의의존의 기여 설명은 행정동 SHAP이 담당)
DEPCOMP = {"A_인프라": "인프라", "B_외출커뮤적은": "외출커뮤적은",
           "C_배달의존": "배달의존", "D_이동저하": "이동저하", "E_독거비율": "독거비율"}
dep_comp = pd.read_csv(ROOT / "Outputs" / "편의의 역설" / "dependency_components.csv",
                       encoding="utf-8-sig")
dep_comp_gu = {
    gu: {clean: float(r[col]) for col, clean in DEPCOMP.items()}
    for gu, r in dep_comp.groupby("자치구")[list(DEPCOMP.keys())].mean().iterrows()
}

# ── 3. 행정동 골격 (자치구 → [행정동 ...]) ─────────────────────────
dong_map: dict[str, list] = {}
for _, row in dep.iterrows():
    dong_map.setdefault(row["자치구"], []).append({
        "행정동코드": str(row["행정동코드"]),
        "행정동": row["행정동"],
        "dependency": float(row["Dependency"]),
        # ↓↓↓ 팀원이 '행정동코드'로 매칭해 채울 부분 (전이예측) ↓↓↓
        "전이확률": None,
        "위험등급": None,
        "shap": [],
    })

# ── 4. 자치구 블록 조립 ────────────────────────────────────────────
profile: dict[str, dict] = {}
for _, row in shadow.iterrows():
    gu = row["자치구"]
    extra = avo_extra.get(gu, {})
    profile[gu] = {
        "자치구코드": extra.get("자치구코드"),               # avoidance_index
        "quadrant": row["Quadrant"],
        "dependency": float(row["Dependency"]),             # 자치구 집계
        "dependency_std": float(row["Dependency_std"]),     # shadow_index
        "avoidance": float(row["Avoidance"]),
        "avoidance_3var": extra.get("avoidance_3var"),       # avoidance_index
        "n_행정동": int(row["n_행정동"]),
        "n_가구주": int(row["n_가구주"]),                    # 표본수
        "n_지역사회": int(row["n_지역사회"]),                # 표본수
        "회피분해": {
            "원본": avo_map.get(gu, {}),                       # 나(avoidance_index 4요소, 원본값)
            # ↓↓↓ 팀원이 채울 부분 (가중치·서울평균으로 산출) ↓↓↓
            "가중편차기여도": {k: None for k in COMP_KEYS},
            "절대가중기여도": {k: None for k in COMP_KEYS},
        },
        "의존분해": {
            "원본": dep_comp_gu.get(gu, {}),                   # 나(dependency_components 5요소, 자치구 평균)
            # 기여도 분해 없음 — 편의의존의 기여 설명은 행정동 SHAP이 담당
        },
        "행정동": dong_map.get(gu, []),                       # dependency_index
    }

# ── 5. 저장 ────────────────────────────────────────────────────────
out_path = OUT_DIR / "gu_profile.json"
out_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

# ── 검증 출력 ──────────────────────────────────────────────────────
total_dong = sum(len(v["행정동"]) for v in profile.values())
print(f"생성: {out_path}")
print(f"   자치구 {len(profile)}개 / 행정동 {total_dong}개 (반올림 없음, 원본값 그대로)")
missing_avo = [gu for gu, v in profile.items() if not v["회피분해"]["원본"]]
if missing_avo:
    print(f"   [경고] 회피분해 없는 자치구: {missing_avo}")
sample = next(iter(profile))
print(f"\n[샘플] {sample}")
preview = dict(profile[sample])
preview["행정동"] = preview["행정동"][:2] + (["...(생략)"] if len(preview["행정동"]) > 2 else [])
print(json.dumps(preview, ensure_ascii=False, indent=2))
