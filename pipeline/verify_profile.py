# -*- coding: utf-8 -*-
"""shadow_profile.json 완전성 검증 (재머지 후 빈칸 남았나 확인)."""
import json
from pathlib import Path

D = Path(__file__).resolve().parent.parent / "Data"
p = json.loads((D / "shadow_profile.json").read_text(encoding="utf-8"))

dong = sum(len(v["행정동"]) for v in p.values())
nd = sum(1 for v in p.values() if not v.get("의존분해", {}).get("원본"))
ng = sum(1 for v in p.values()
         if v["회피분해"]["가중편차기여도"].get("복지불신") is None)
nj = sum(1 for v in p.values() for d in v["행정동"] if d.get("전이확률") is None)
ns = sum(1 for v in p.values() for d in v["행정동"] if not d.get("shap"))

print(f"자치구 {len(p)} / 행정동 {dong}")
print(f"빈칸 — 의존분해:{nd}  회피기여도:{ng}  전이확률:{nj}  SHAP:{ns}")
print("전부 채워짐" if nd + ng + nj + ns == 0 else "!! 빈칸 있음")
