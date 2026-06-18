# -*- coding: utf-8 -*-
"""
베이스라인 회귀 체크 — 팀 데이터/규칙 드리프트 감지.

build_prescription_input.py 는 API 없이 결정론적이므로,
같은 데이터면 누구나 같은 입력 JSON이 나와야 한다.
이 스크립트는 지금 환경의 결과를 baseline/ 기준과 비교한다.

  python check_baseline.py 노원구            # 비교 (차이 있으면 exit 1)
  python check_baseline.py 노원구 --update   # 현재 결과를 새 기준으로 저장(의도적 변경 후)
"""
import json, sys, io, os

if hasattr(sys.stdout, "buffer") and (getattr(sys.stdout, "encoding", "") or "").lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import build_prescription_input as eng

BASE = os.path.dirname(os.path.abspath(__file__))
BDIR = os.path.join(BASE, "baseline")


def norm(o):
    """비교용 정규화 — _relevance 등 표시용 필드 제외하고 정렬된 JSON 문자열."""
    return json.dumps(o, ensure_ascii=False, sort_keys=True)


def main():
    gu = sys.argv[1] if len(sys.argv) > 1 else "노원구"
    update = "--update" in sys.argv
    os.makedirs(BDIR, exist_ok=True)
    bpath = os.path.join(BDIR, f"처방입력_{gu}.baseline.json")

    cur = eng.build(gu)

    if update or not os.path.exists(bpath):
        json.dump(cur, open(bpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"✅ 베이스라인 저장: {bpath}")
        return

    base = json.load(open(bpath, encoding="utf-8"))
    if norm(cur) == norm(base):
        print(f"✅ [{gu}] 베이스라인 일치 — 데이터·규칙 동기화됨.")
        return

    print(f"❌ [{gu}] 베이스라인과 다름! 데이터(ontology/programs/shadow_profile)나 규칙이 어긋남.")
    # 어느 섹션이 다른지 간단 요약
    for key in ("현행_제도", "진단", "이식후보", "지역_프로파일"):
        if norm(cur.get(key)) != norm(base.get(key)):
            cn = len(cur.get(key, [])) if isinstance(cur.get(key), list) else "·"
            bn = len(base.get(key, [])) if isinstance(base.get(key), list) else "·"
            print(f"   - '{key}' 변경됨 (기준 {bn} → 현재 {cn})")
    print("   의도한 변경이면:  python check_baseline.py", gu, "--update")
    sys.exit(1)


if __name__ == "__main__":
    main()
