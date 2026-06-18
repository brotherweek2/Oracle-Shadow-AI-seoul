# -*- coding: utf-8 -*-
"""
SHADOW 처방 엔진 — 그래프(ontology) 규칙으로 LLM 입력 JSON 생성.

★ 데이터 소스 (최종본, 단일 원천) ──────────────────────────
  ontology.json        : 규칙(충돌·need·이식·coverage). gender·beneficiary 포함.
  programs.json        : 제도 2403건 완전체 (서울+국내타지역+해외, 코드·gender·beneficiary 태깅 완료).
                         region_scope 로 구분: 서울자치구/서울전체 = 서울, 국내지역 = 국내타지역, 국가 = 해외.
  shadow_profile.json  : 자치구별 quadrant(Q프로필) + 회피/의존 주동인 + 고위험 행정동(SHAP).
                         → Q를 하드코딩하지 않고 자치구 프로파일에서 자동으로 가져옴.

입력: 자치구명  (Q는 shadow_profile에서 자동. 2번째 인자로 강제 override 가능)
출력: 처방입력_<자치구>.json  (①현행/②한계/③need/④이식후보/근거논문 + 지역프로파일 전부 계산됨)

LLM은 이 JSON을 받아 글만 쓴다 (계산 안 함 → 환각 차단).

실행(한글경로·콘솔깨짐 함정 회피):
  $env:PYTHONIOENCODING="utf-8"
  C:/Users/brotherweek/AppData/Local/Programs/Python/Python312/python.exe build_prescription_input.py 노원구
  C:/.../python.exe build_prescription_input.py 노원구 Q1   # Q 강제 지정(테스트용)
"""
import json, sys, io, os
from collections import OrderedDict

if hasattr(sys.stdout, "buffer") and (getattr(sys.stdout, "encoding", "") or "").lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = os.path.dirname(os.path.abspath(__file__))
def L(name): return json.load(open(os.path.join(BASE, name), encoding="utf-8"))

ONT      = L("ontology.json")
EVIDENCE = L("evidence.json")
PROGRAMS = L("programs.json")          # ★ 단일 원천 (서울+타지역+해외)
PROFILE  = L("shadow_profile.json")    # ★ 자치구별 Q·프로파일

SENS = ONT["quadrant_sensitive_stigma"]
VULN = ONT["quadrant_vulnerable_dependency"]
LIMIT_TO_NEED = ONT["limit_to_needs"]

SEOUL_SCOPES = {"서울자치구", "서울전체"}
SEOUL_WIDE = {"서울전체", "서울시"}          # 자치구 비귀속으로 보는 광역값(regions 기준)
OK_GENDER = {"무관", "남성"}                  # coverage_rule: 5060 '남성'
OK_AGE = {"중장년", "전연령"}

STG_NAME = {e["id"]: e["name"] for e in ONT["stigma_elements"]}
DEP_NAME = {e["id"]: e["name"] for e in ONT["dependency_elements"]}


# ── 서울/이식 풀 구분 ────────────────────────────────────────
def is_seoul(p):
    return p.get("region_scope") in SEOUL_SCOPES

def in_gu(p, gu):
    reg = set(p.get("regions", []))
    return (gu in reg) or (reg & SEOUL_WIDE) or (p.get("region_scope") == "서울전체")


def is_current(p, gu):
    """coverage_rule.is_current — 5060 남성 당사자에게 현행으로 인정되나.
    regions(자치구/서울전체) AND target_age(중장년/전연령) AND gender(무관/남성) AND beneficiary(당사자)."""
    age_ok = bool(set(p.get("target_age", [])) & OK_AGE)
    gender_ok = p.get("gender", "무관") in OK_GENDER
    benef_ok = p.get("beneficiary", "당사자") == "당사자"
    return in_gu(p, gu) and age_ok and gender_ok and benef_ok


def conflicts(p, qs):
    """제도 p가 선택 Q들에 일으키는 낙인/의존 충돌 코드 집합."""
    stg_hit, dep_hit = set(), set()
    for q in qs:
        stg_hit |= set(p.get("stimulates_stigma", [])) & set(SENS.get(q, []))
        dep_hit |= set(p.get("deepens_dependency", [])) & set(VULN.get(q, []))
    return stg_hit, dep_hit


def evidence_for(trigger_codes, need_id, top=4):
    """supports_ids 매칭 논문을 관련도순 정예 추림. 트리거(STG/DEP) 직접일치=+2, need일치=+1."""
    scored = []
    for e in EVIDENCE:
        sids = set(e.get("supports_ids", []))
        score = 2 * len(sids & set(trigger_codes)) + (1 if need_id in sids else 0)
        if score <= 0:
            continue
        scored.append((score, e))
    scored.sort(key=lambda x: (-x[0], x[1].get("scope", ""), -int(x[1].get("year", 0) or 0)))
    out = []
    for score, e in scored[:top]:
        out.append(OrderedDict([
            ("evidence_id", e["evidence_id"]), ("title", e["title"]),
            ("authors", e.get("authors", "")), ("year", e.get("year", "")),
            ("scope", e.get("scope", "")), ("key_finding", e.get("key_finding", "")),
            ("url", e.get("url", "")), ("_relevance", score),
        ]))
    return out


def ref_priority(p):
    s = p.get("region_scope", "")
    if s == "국가":   return "해외"
    if s == "국내지역": return "국내타지역"
    return "서울타자치구"


def transplant_candidates(need_id, gu, qs):
    """transplant_rule: fulfills_needs ∋ need AND 선택Q 무충돌 AND 선택 자치구 미시행."""
    cands = []
    for p in PROGRAMS:
        if need_id not in p.get("fulfills_needs", []):
            continue
        if in_gu(p, gu):                          # 이미 그 자치구 시행 → 이식 불필요
            continue
        stg, dep = conflicts(p, qs)
        if stg or dep:                            # 선택 Q에 충돌하면 이식후보 자격 상실
            continue
        cands.append(OrderedDict([
            ("program_id", p["program_id"]), ("name", p["name"]),
            ("regions", p.get("regions", [])), ("region_scope", p.get("region_scope", "")),
            ("reference_priority", ref_priority(p)), ("rationale", p.get("rationale", "")),
            ("status", p.get("status", "")), ("evidence_ids", p.get("evidence_ids", [])),
        ]))
    by_tier = {"해외": [], "국내타지역": [], "서울타자치구": []}
    for c in cands:
        by_tier.setdefault(c["reference_priority"], []).append(c)
    mixed = []
    for tier in ("해외", "국내타지역", "서울타자치구"):
        mixed.extend(by_tier[tier][:3])
    order = {"해외": 0, "국내타지역": 1, "서울타자치구": 2}
    mixed.sort(key=lambda c: order.get(c["reference_priority"], 9))
    return mixed


def topk(d, k=3):
    """dict(value=숫자)에서 값 큰 순 키 k개."""
    return [name for name, _ in sorted(d.items(), key=lambda kv: -kv[1])[:k]]


def region_profile(gu, q):
    """shadow_profile에서 자치구 진단 맥락 추출 (LLM이 ②⑤를 구체적으로 쓰도록)."""
    pr = PROFILE.get(gu, {})
    if not pr:
        return OrderedDict([("quadrant", q), ("_note", "shadow_profile에 해당 자치구 없음")])
    회피 = pr.get("회피분해", {}).get("가중편차기여도") or pr.get("회피분해", {}).get("원본", {})
    의존 = pr.get("의존분해", {}).get("원본", {})
    동 = pr.get("행정동", [])
    고위험 = [d for d in 동 if d.get("위험등급") in ("최고위험", "고위험")]
    고위험.sort(key=lambda d: -(d.get("전이확률") or 0))
    위험동 = [OrderedDict([
        ("행정동", d["행정동"]), ("위험등급", d.get("위험등급")),
        ("주요위험요인", (d.get("shap") or [{}])[0].get("feature_label", "")),
    ]) for d in 고위험[:4]]
    return OrderedDict([
        ("quadrant", q),
        ("quadrant_민감낙인", [STG_NAME.get(c, c) for c in SENS.get(q, [])]),
        ("quadrant_취약의존", [DEP_NAME.get(c, c) for c in VULN.get(q, [])]),
        ("회피점수", pr.get("avoidance")),
        ("의존점수", pr.get("dependency")),
        ("회피_주동인", topk(회피)),
        ("의존_주동인", topk(의존)),
        ("고위험_행정동", 위험동),
    ])


def build(gu, q_override=None):
    q = q_override or PROFILE.get(gu, {}).get("quadrant")
    if not q:
        raise SystemExit(f"❌ shadow_profile.json에 '{gu}'의 quadrant가 없습니다. (자치구명 확인)")
    qs = [q]

    gu_progs = [p for p in PROGRAMS if is_seoul(p) and in_gu(p, gu)]

    # ① 현행
    현행 = [OrderedDict([("program_id", p["program_id"]), ("name", p["name"]),
                        ("fulfills_needs", p.get("fulfills_needs", []))])
           for p in gu_progs if is_current(p, gu)]

    # ② 한계 → ③ need → 근거논문
    buckets = OrderedDict()
    def add(한계, prog, codes):
        b = buckets.setdefault(한계, {"원인_제도": [], "codes": set()})
        b["codes"] |= set(codes)
        entry = OrderedDict([("program_id", prog["program_id"]), ("name", prog["name"])])
        if 한계 == "낙인충돌":
            entry["stimulates_stigma"] = [c for c in prog.get("stimulates_stigma", []) if c in codes]
        elif 한계 == "의존심화":
            entry["deepens_dependency"] = [c for c in prog.get("deepens_dependency", []) if c in codes]
        elif 한계 == "중복배제":
            entry["access_mode"] = prog.get("access_mode")
        elif 한계 == "자치구귀속":
            entry["regions"] = prog.get("regions", [])
        b["원인_제도"].append(entry)

    for p in gu_progs:
        stg, dep = conflicts(p, qs)
        if stg: add("낙인충돌", p, stg)
        if dep: add("의존심화", p, dep)
        if p.get("region_scope") != "서울전체" and not (set(p.get("regions", [])) & SEOUL_WIDE):
            add("자치구귀속", p, ["NEED_Transferable"])
        if p.get("access_mode") == "중복배제":
            add("중복배제", p, ["NEED_UniversalAccess"])

    진단 = []
    for 한계, b in buckets.items():
        need = LIMIT_TO_NEED[한계]
        need_id = need["need_id"]
        trigger = {c for c in b["codes"] if c.startswith(("STG_", "DEP_"))}
        진단.append(OrderedDict([
            ("한계", 한계),
            ("원인_제도", b["원인_제도"][:8]),
            ("원인_제도_총수", len(b["원인_제도"])),
            ("need", OrderedDict([("id", need_id), ("name", need["name"]), ("def", need["def"])])),
            ("근거_논문", evidence_for(trigger, need_id)),
        ]))

    # ④ 이식후보
    need_ids = []
    for d in 진단:
        nid = d["need"]["id"]
        if nid not in need_ids: need_ids.append(nid)
    이식후보 = [OrderedDict([("need_id", nid),
                          ("candidates", transplant_candidates(nid, gu, qs)[:6])])
              for nid in need_ids]

    return OrderedDict([
        ("선택_자치구", gu),
        ("대상", "서울 5060 남성 1인가구"),
        ("지역_프로파일", region_profile(gu, q)),
        ("현행_제도", 현행),
        ("진단", 진단),
        ("이식후보", 이식후보),
        ("_note", "ontology 규칙으로 계산됨. LLM은 재판단 말고 ①~⑤ 서술만. 입력에 없는 제도·논문 인용 금지."),
    ])


def main():
    gu = sys.argv[1] if len(sys.argv) > 1 else "노원구"
    q_override = sys.argv[2] if len(sys.argv) > 2 else None
    result = build(gu, q_override)
    out = os.path.join(BASE, f"처방입력_{gu}.json")
    json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    rp = result["지역_프로파일"]
    print(f"[{gu}] Q={rp['quadrant']} | 회피주동인={rp.get('회피_주동인')} | 고위험동={[d['행정동'] for d in rp.get('고위험_행정동',[])]}")
    print(f"  ① 현행 제도: {len(result['현행_제도'])}건")
    for d in result["진단"]:
        print(f"  ② {d['한계']}: 원인 {d['원인_제도_총수']}건 → ③ {d['need']['name']}({d['need']['id']}) · 근거논문 {len(d['근거_논문'])}편")
    for t in result["이식후보"]:
        pr = {}
        for c in t["candidates"]:
            pr[c["reference_priority"]] = pr.get(c["reference_priority"], 0) + 1
        print(f"  ④ {t['need_id']} 이식후보: {len(t['candidates'])}건 {pr}")
    print(f"  → 저장: {out}")


if __name__ == "__main__":
    main()
