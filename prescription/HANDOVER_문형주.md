# 인수인계 — 서울시 1인가구 프로그램 enrich (담당: 문형주)

> 새 대화/세션이 이 파일만 읽으면 맥락을 바로 잡고 이어갈 수 있도록 작성. (작성 시점 기준 작업 완료 상태)

---

## 0. 한 줄 요약
**문형주 담당 구간 P-0917~P-1374 (P-1019 SKIP 제외) = 457건 enrich 분류·검증 100% 완료.** 최종 산출물 `programs_enriched_문형주.json` 디스크 저장됨. 오류 0, 검증 통과.

---

## 1. 이 프로젝트가 뭔가 (배경)
- 프로젝트: **SHADOW-AI / SHADOW-MAP (팀 Alonear)** — 서울 5060 남성 1인가구의 "보이지 않는 고립(고독사)" 진단·처방.
- 이 작업은 그 처방 파이프라인의 **① 현재 제도 데이터**를 만드는 빌드타임 LLM 태깅.
- 목표: 각 제도가 우리 타깃(5060 남성 1인가구)에게 일으키는 **② 한계**(낙인충돌/의존심화/연령·지역 불일치/중복배제)가 드러나는 데이터 생성.
- 작업 명세 원본: `AGENT_PROMPT_programs_enrich.md`. 코드·규칙 단일원천: `ontology.json`. 표준 예시: `gold_examples.json`(16건).

## 2. 입력 파일 (모두 `c:\Users\brotherweek\Desktop\0610\`)
| 파일 | 역할 |
| --- | --- |
| `programs.json` | 제도 골격 1,743건 (읽기전용, program_id·regions 잠금) |
| `ontology.json` | 코드·규칙 단일 원천 (tagging_guide rule1~9) |
| `gold_examples.json` | 표준 16건 (톤·태깅강도 기준) |
| `서울시 1인가구 참여프로그램 현황 2025/2026.csv` | 원자료 (CP949 인코딩) |
| `SKIP_골드16.txt` | 건너뛸 16건 (내 구간은 P-1019 1건) |

## 3. ⚠️ 환경 함정 (반드시 숙지)
- **Python 경로**: `python`/`py` 직접 호출하면 한글 경로 mangling으로 실패. **반드시 풀패스 사용**:
  `C:/Users/brotherweek/AppData/Local/Programs/Python/Python312/python.exe`
- **콘솔 출력 깨짐**: UTF-8 출력 시 `PYTHONIOENCODING=utf-8` 환경변수 설정. 데이터는 정상, 표시만 깨지는 것.
- **CSV**: `encoding="cp949", errors="replace"` + `csv.field_size_limit(2147483647)` (Windows에서 sys.maxsize는 OverflowError).
- **extract_source.py**: 원래 `work/` 하위에 사는 설계(BASE가 두 단계 상위). 그래서 `work/`로 복사해 실행함. CSV·programs.json은 `0610` 루트 참조.

## 4. 작업 디렉토리 구조 (`0610/work/`)
```
work/
  extract_source.py     # CSV 원문 재결합 (0610에서 복사, work/에 위치해야 BASE 맞음)
  show.py               # source_916_1374.json[start:start+count] → view.txt (콘솔 깨짐 회피)
  write_batch.py        # enriched_in.json → enriched/<id>.json 원자적 기록 + checkpoint + run.log (enum 즉시검증)
  verify_merge.py       # §8 검증 + 병합 → 최종 산출물 3종
  source_916_1374.json  # 내 구간 458건 CSV 원문 (0 unmatched)
  enriched/             # 제도 1건=파일 1개 (457개) ← 재개 단위
  checkpoint.json       # {total, done[...457 IDs], failed, updated_at}
  run.log               # DONE P-XXXX 로그
  decisions_문형주.md   # ★판단 로그 (rule1~9 외 애매 케이스 일관 기준 전부)
  enriched_in.json      # 마지막 배치 입력 (재사용 가능)
  view.txt              # 마지막 show.py 출력
```

## 5. 최종 산출물 (`0610/` 루트)
| 파일 | 내용 |
| --- | --- |
| **`programs_enriched_문형주.json`** | ⭐ 제출용 최종본 457건 (스키마 일치, _audit·_meta 제거) |
| `programs_audit_문형주.json` | 제도별 분류 근거메모 (program_id→_audit) |
| `verification_report_문형주.md` / `.json` | §8 검증 리포트 |
| `HANDOVER_문형주.md` | 이 파일 |

## 6. 검증 결과 (모두 통과)
- **✅ 검증 통과 / 오류 0 / 경고 71(전부 무해)**. 경고 = 명칭기반 주석 "(원본 본문 없음…)"의 '회원제'·'전문의'의 '문의' 정규식 오탐 69 + 동일명 회차 2.
- 3파일 교차정합 확인됨: enriched↔audit(누락 0, 근거 없는 코드 0, 과잉메모 0), report↔enriched(통계 100% 재계산 일치), decisions↔enriched(7개 핵심 규칙 위반 0).
- **분포**: access 보편434/중복배제18/선별5 · STG_FaceExposure 438 · NEED_RelationRestore 250 · 연령빈틈 56 · 비대면/위기선별/무낙인 희소(ontology 예측과 일치) · 무한계 제도 0(자치구귀속이 항상 잡힘).

## 7. 핵심 판단 규칙 (요약 — 상세는 `work/decisions_문형주.md`)
- **대면 기본값(rule8)**: 본문/명칭에 비대면(온라인·화상·ZOOM·앱·전화·배송) 명시 없으면 대면 간주 → STG_FaceExposure. ("온라인 접수"는 신청채널, 전달방식 아님)
- **소셜다이닝/혼밥탈출/행복한밥상/공동조리·나눔** → NEED_RelationRestore(a). **요리강습(나눠먹기·소통 명시 없음)** → 빈값 (gold P-0114).
- **자립역량 교육**(디지털·재무/경제·주거/임대차·집수리·정리수납·노동/세무·취업) → NEED_RelationRestore(b). **건강·체력·정서·취미·여가·명상·공연관람·강연** → 빈값.
- **동아리/클럽/크루/봉사단/정기모임**(지속 커뮤니티) → RelationRestore(a). **일회성 강습/클래스** → 빈값.
- **비대면 완결**(앱·화상·배송 챌린지) → DEP_NoContact+NoOuting, 보편·생활언어면 NEED_NoStigma 동반.
- **일방 물품 지급**(식재료/상품권/웰컴박스/햇반) → DEP_NoRelation, 수령은 집합 아님→FaceExposure 미부여.
- **★중복배제(access_mode) 최종 기준**: (a)소득/수급/기초생활 제외, (b)타 자치구/타 기관 동일사업 수혜자 제외, (c)타 named 사업/서비스(홈스윗홈·싱글싱글스페셜·끼리끼리) 수혜자 제외, (d)연속 N년. → **같은 센터의 기수/회차/강좌 회전(신규 우선)은 보편.**
- **STG_RecipientIdentity**: 고독사위험·고립청년·돌봄청년 등 특정 취약군 발굴·선별 명시 때만. '외로움 느끼는'·'독거 어르신'(연령세그먼트)·'노부모 부양 포함'(확대문구)은 미부여.
- **target_age 보정(rule7)**: csv 모집연령/제목 기준. 성동/도봉 행복한밥상 "1958~1985년생(만40~67)"은 노인 포함 → [중장년,노인].

## 8. 재개/재검증 명령 (필요 시)
```bash
PY="C:/Users/brotherweek/AppData/Local/Programs/Python/Python312/python.exe"
cd "c:/Users/brotherweek/Desktop/0610/work"
# 진행상태 확인
PYTHONIOENCODING=utf-8 "$PY" -c "import json;cp=json.load(open('checkpoint.json',encoding='utf-8'));print('done',len(cp['done']),cp['done'][-3:])"
# 특정 구간 원문 보기 (인덱스: source 배열 0=P-0917)
PYTHONIOENCODING=utf-8 "$PY" show.py <start> <count>   # → work/view.txt 읽기
# (미완 시) enriched_in.json 작성 후 저장
PYTHONIOENCODING=utf-8 "$PY" write_batch.py
# 전체 재검증·재병합
PYTHONIOENCODING=utf-8 "$PY" verify_merge.py
```
**멱등 재개**: checkpoint.json + enriched/ 스캔으로 done 복원 → 미처리 최소 ID부터. 같은 입력=같은 결과.

## 9. 알려진 한계 (사람 검수 우선순위)
1. 단일 LLM 1패스 분류. 경계 판정(중복배제 18건, 동아리 vs 일회성, 소셜다이닝 vs 요리강습)은 일관되나 다른 견해 여지.
2. 본문 없는 ~50건+(특히 양천구 79건 회원제 보일러플레이트)는 **명칭 기반 추론** → 신뢰도 낮음, `_audit`에 표기됨.
3. FaceExposure 96%·보편 95% 거의 균일(rule8 디폴트 효과). 변별력은 target_age·fulfills_needs·access_mode에서 나옴.

## 10. 다음 단계 (4명 병합 시)
- 사람1(P-0001~0458)/사람2(P-0459~0916)/사람4(P-1375~1833)의 결과와 합쳐 1,743건 완성.
- 각자의 `decisions_*.md`를 비교해 **중복배제 기준·대면 기본값·소셜다이닝 경계**를 통일하고 `tagging_guide`에 흡수.
- 양천구 명칭기반 50여 건은 사람이 명칭만 빠르게 재확인 권장.
