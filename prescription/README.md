# SHADOW 처방 파이프라인 (팀 공유용)

서울 5060 남성 1인가구 고립 → **자치구별 복지 처방문(①~⑤)** 자동 생성.
**그래프(규칙 계산) → LLM(글쓰기)** 2단 구조. LLM은 계산하지 않고, 그래프가 뽑은 재료만 자연어로 엮는다(환각 차단).

> 이 파이프라인은 저장소의 `prescription/` 폴더에 자기완결형으로 들어있다. **`prescription/`에서 실행**한다.

---

## 1. 빠른 시작

```powershell
cd prescription

# (1) 의존성
pip install -r requirements.txt          # openai

# (2) OpenAI 키 — 각자 본인 키, 코드/깃에 절대 넣지 말 것
$env:OPENAI_API_KEY = "sk-..."
$env:PYTHONIOENCODING = "utf-8"      # 한글 콘솔 깨짐 방지

# (3) 자치구 하나 처방 (예: 노원구 — <자치구명> 자리에 강남구 등 25개구)
python build_prescription_input.py 노원구      # 그래프 계산 → 처방입력_노원구.json
python generate_prescription.py 노원구          # OpenAI 호출 → 처방문_노원구.md
```

> ⚠️ Windows에서 `python`이 한글 경로로 깨지면 풀패스 사용:
> `C:/Users/<id>/AppData/Local/Programs/Python/Python312/python.exe`

---

## 2. 데이터 소스 (단일 원천 — 이 3개만 고치면 결과가 바뀐다)

| 파일 | 역할 |
| --- | --- |
| `ontology.json` | 규칙(충돌·need·이식·coverage). gender·beneficiary 4조건 |
| `programs.json` | 제도 2403건 완전체 (서울+국내타지역+해외). `region_scope`로 구분 |
| `shadow_profile.json` | 자치구별 `quadrant`(Q) + 회피/의존 주동인 + 고위험 행정동 |
| `evidence.json` | 근거 논문. `supports_ids`로 DEP/NEED/STG 노드에 연결 |

엔진은 **돌릴 때마다 이 파일들을 새로 읽는다**(캐시 없음). 고치면 다음 실행에 자동 반영.
`programs_enriched_*.json`은 **더 이상 안 씀**(programs.json이 흡수).

---

## 3. 파이프라인 흐름

```
자치구명 ─▶ build_prescription_input.py
              │  ① 현행(coverage_rule) / ② 한계(conflict+structural)
              │  ③ need(limit_to_needs) / ④ 이식후보(transplant_rule)
              │  + 근거논문 매칭 + 지역_프로파일(shadow_profile)
              ▼
        처방입력_<자치구>.json   ← 결정론적(API 불필요). 베이스라인 비교 대상.
              │
              ▼  generate_prescription.py (gpt-4o)
        처방문_<자치구>.md       ← 최종 처방문 ①~⑤
```

설계 상세: `처방_LLM_PROMPT.md`

---

## 4. 베이스라인 (팀 동기화 기준) ★

`build_prescription_input.py`는 **API 없이 결정론적**이라, 같은 데이터면 누구나 같은 결과가 나와야 한다.

- **기준 파일**: `baseline/처방입력_노원구.baseline.json`
- **확인법**: 본인 환경에서 아래를 돌려 차이가 없어야 정상.
  ```powershell
  python check_baseline.py 노원구
  ```
- **차이가 나면** = 데이터(ontology/programs/shadow_profile)나 규칙이 서로 어긋난 것.
  누가 무엇을 고쳤는지 맞춰야 함. (4명이 동시에 데이터 편집할 때 드리프트 감지용)

> 처방문(.md)은 LLM이라 매번 미세하게 달라짐 → 베이스라인 비교는 **입력 JSON으로만** 한다.

---

## 5. 공유 규칙

- ✅ 공유: 위 §2 데이터 4개 + 스크립트 + README + baseline/ (총 ~4MB)
- ❌ 제외: 원본 CSV(121MB, 엔진이 안 읽음), `OPENAI_API_KEY`, `처방입력_*.json`·`처방문_*.json`(생성물), `work/`
- 키는 **각자 발급**해서 각자 환경변수로. 절대 파일·깃·채팅에 넣지 말 것.
