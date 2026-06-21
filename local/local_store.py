# -*- coding: utf-8 -*-
"""
local_store.py — 오프라인(로컬) 데이터 백엔드.

shadow_rag_llm.py 가 ADB(Oracle Autonomous Database)에서 하던 사실 추출을,
같은 결과가 나오도록 로컬 JSON(Data/Prescription/*.json)으로 재현한다.

ADB의 '그래프 추론'은 사실 복잡한 그래프 DB 기능이 아니라 집합 연산이다:
  - 엣지 테이블(STIMULATES_E·SENSITIVE_E·DEEPENS_E·VULNERABLE_E·FULFILLS_E·IN_REGION_E)은
    programs.json 의 배열 필드 + ontology.json 의 Q별 민감/취약 매핑을 펼친 것뿐.
  - 따라서 JSON을 읽어 set 교집합/배제로 동일하게 계산할 수 있다.

shadow_rag_llm.py 의 함수들과 '같은 시그니처'를 제공해 그대로 갈아끼운다.
(cur 인자는 호환을 위해 받기만 하고 쓰지 않는다.)

활성화: 환경변수 SHADOW_LOCAL=1  (shadow_rag_llm.py 가 분기)
"""
import os
import json
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PRESC = os.path.join(ROOT, "Data", "Prescription")


def _load(name):
    with open(os.path.join(PRESC, name), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _data():
    """ontology / shadow_profile / programs / evidence 4종을 1회 로드 후 캐시."""
    ont = _load("ontology.json")
    profile = _load("shadow_profile.json")
    programs = _load("programs.json")
    evidence = _load("evidence.json")
    return ont, profile, programs, evidence


# ── ADB 커서 흉내 (인라인 단순 SELECT만 처리) ────────────────────────
# shadow_chat.build_chat_context 가 cur.execute("SELECT DATA FROM SHADOW_PROFILE")
# 를 직접 호출하므로, 그 단순 케이스만 지원한다.
class LocalCur:
    def __init__(self):
        self._rows = []

    def execute(self, sql, *args, **kwargs):
        s = " ".join(str(sql).split()).upper()
        ont, profile, programs, evidence = _data()
        if "FROM SHADOW_PROFILE" in s:
            self._rows = [(profile,)]
        elif "FROM ONTOLOGY" in s:
            self._rows = [(ont,)]
        elif "FROM EVIDENCE" in s:
            self._rows = [(e,) for e in evidence]
        else:
            # 복잡한 쿼리는 함수 단위로 이미 대체되므로 여기로 오지 않는다.
            self._rows = []
        return self

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class LocalConn:
    def cursor(self):
        return LocalCur()

    def close(self):
        pass


def connect():
    """ADB 접속 대체 — 로컬 더미 커넥션."""
    return LocalConn()


# ── 사실 추출 (shadow_rag_llm 의 ADB 함수들과 동일 시그니처) ──────────
def load_rules_and_profile(cur=None):
    ont, profile, _, _ = _data()
    return ont, profile


def _norm_program(p):
    """gu_programs 가 ADB에서 뽑던 필드 + 기본값(무관/당사자)을 그대로 맞춘다."""
    return {
        "program_id": p.get("program_id"),
        "name": p.get("name"),
        "access_mode": p.get("access_mode"),
        "gender": p.get("gender") or "무관",
        "beneficiary": p.get("beneficiary") or "당사자",
        "region_scope": p.get("region_scope"),
        "regions": p.get("regions") or [],
        "target_age": p.get("target_age") or [],
        "stimulates_stigma": p.get("stimulates_stigma") or [],
        "deepens_dependency": p.get("deepens_dependency") or [],
        "fulfills_needs": p.get("fulfills_needs") or [],
    }


def gu_programs(cur, gu):
    """선택 자치구에서 시행 중(또는 서울전체)인 제도.
    원본 SQL WHERE 재현:
      region_scope IN ('서울자치구','서울전체')
      AND ( gu ∈ regions  OR  '서울전체' ∈ regions  OR  region_scope='서울전체' )
    """
    _, _, programs, _ = _data()
    out = []
    for p in programs:
        rs = p.get("region_scope")
        if rs not in ("서울자치구", "서울전체"):
            continue
        regions = p.get("regions") or []
        if (gu in regions) or ("서울전체" in regions) or (rs == "서울전체"):
            out.append(_norm_program(p))
    return out


def transplant(cur, need_id, gu, q):
    """그래프 추론 재현:
       need 충족(FULFILLS) ∧ region_scope≠서울전체 ∧ 그 자치구 미시행(¬IN_REGION)
       ∧ 선택 Q가 민감한 낙인 무자극(¬(STIMULATES ∩ SENSITIVE[q]))
       ∧ 선택 Q가 취약한 의존 무심화(¬(DEEPENS ∩ VULNERABLE[q]))
    """
    ont, _, programs, _ = _data()
    sset = set(ont["quadrant_sensitive_stigma"].get(q, []))
    vset = set(ont["quadrant_vulnerable_dependency"].get(q, []))
    out = []
    for p in programs:
        if need_id not in (p.get("fulfills_needs") or []):
            continue
        if p.get("region_scope") == "서울전체":
            continue
        if gu in (p.get("regions") or []):
            continue
        if set(p.get("stimulates_stigma") or []) & sset:
            continue
        if set(p.get("deepens_dependency") or []) & vset:
            continue
        out.append({
            "program_id": p.get("program_id"),
            "name": p.get("name"),
            "region_scope": p.get("region_scope"),
        })
    return out


def fetch_meta(cur, ids):
    """이식후보 program_id들의 regions/rationale/evidence_ids/status 일괄 조회."""
    if not ids:
        return {}
    _, _, programs, _ = _data()
    idset = set(ids)
    out = {}
    for p in programs:
        pid = p.get("program_id")
        if pid in idset:
            out[pid] = {
                "regions": p.get("regions") or [],
                "rationale": p.get("rationale") or "",
                "evidence_ids": p.get("evidence_ids") or [],
                "status": p.get("status") or "",
            }
    return out


def load_evidence(cur=None):
    _, _, _, evidence = _data()
    return evidence
