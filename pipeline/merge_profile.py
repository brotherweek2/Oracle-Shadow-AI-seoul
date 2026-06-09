# -*- coding: utf-8 -*-
"""
최종 프로파일 병합
==================
베이스 = 팀원 gu_profile_y.json  (전이예측·SHAP·회피 기여도 채워짐)
추가   = 우리 gu_profile.json 의 '의존분해' (편의의존 5요소 원본)

→ 진단 + 회피분해(기여도) + 의존분해(원본) + 행정동(전이·SHAP) 통합
출력: Data/shadow_profile.json
"""
import json
from pathlib import Path

D = Path(__file__).resolve().parent.parent / "Data"   # pipeline/ → 레포 루트/Data
team = json.loads((D / "gu_profile_y.json").read_text(encoding="utf-8"))
ours = json.loads((D / "gu_profile.json").read_text(encoding="utf-8"))

final = {}
missing_dep, missing_gu = [], []
for gu, block in team.items():
    dep_block = ours.get(gu, {}).get("의존분해")
    if dep_block is None:
        missing_dep.append(gu)
    # 키 순서 보존: 회피분해 바로 뒤에 의존분해 삽입
    new_block = {}
    for k, v in block.items():
        new_block[k] = v
        if k == "회피분해" and dep_block is not None:
            new_block["의존분해"] = dep_block
    if dep_block is not None and "의존분해" not in new_block:
        new_block["의존분해"] = dep_block  # 회피분해 없던 경우 안전망
    final[gu] = new_block

# 우리엔 있는데 팀원 파일에 없는 자치구 점검
for gu in ours:
    if gu not in team:
        missing_gu.append(gu)

out = D / "shadow_profile.json"
out.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"생성: {out}")
print(f"  자치구 {len(final)}개")
if missing_dep:
    print(f"  ⚠️ 의존분해 못 찾은 자치구: {missing_dep}")
if missing_gu:
    print(f"  ⚠️ 팀원 파일에 없는 자치구: {missing_gu}")
print(f"  의존분해 병합됨: {len(final) - len(missing_dep)}/{len(final)}")

# 검증: 강남구가 4개 다 갖췄나
gu = "강남구"
b = final[gu]
print(f"\n[검증] {gu} 자치구레벨 키:", list(b.keys()))
print("  회피분해 기여도 채워짐?:", b["회피분해"]["가중편차기여도"]["복지불신"] is not None)
print("  의존분해 원본 있음?:", "원본" in b.get("의존분해", {}))
print("  행정동[0] 전이확률 채워짐?:", b["행정동"][0]["전이확률"] is not None)
print("  행정동[0] SHAP 채워짐?:", len(b["행정동"][0]["shap"]) > 0)
