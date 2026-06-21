# local/ — 오프라인(로컬) 데모 모드

Oracle Cloud(ADB)를 끈 상태에서도 대시보드를 돌려 **스크린샷·시연**을 할 수 있게 한
로컬 백엔드다. ADB가 하던 처방 사실추출(그래프 추론)을 `Data/Prescription/*.json`을
읽어 **집합 연산으로 동일하게 재현**한다. (Oracle 과금 0)

## 구성
- `local_store.py` — ADB 함수(`connect`/`load_rules_and_profile`/`gu_programs`/`transplant`/`fetch_meta`/`load_evidence`)를 로컬 JSON 버전으로 대체
- `run_local.py` — `SHADOW_LOCAL=1` 로 대시보드 실행
- 기존 코드(`shadow_rag_llm.py`)는 `SHADOW_LOCAL=1` 일 때만 이쪽으로 분기 (ADB 모드는 그대로 보존)

## 실행
```
python local/run_local.py
```
또는 직접:
```
# Windows PowerShell
$env:SHADOW_LOCAL=1; python -m streamlit run shadow_service.py
# bash
SHADOW_LOCAL=1 python -m streamlit run shadow_service.py
```
→ 브라우저에서 http://localhost:8501

## 동작 범위 (중요)
- **ADB 없이 되는 것**: 진단맵(SHADOW Map)·전이예측(SHADOW AI)·처방 '사실'(진단/한계/이식후보)·지식그래프 시각화
- **OPENAI_API_KEY 필요**: 처방문 '텍스트' 생성, 담당자 챗봇 답변
  (`.env` 에 `OPENAI_API_KEY=...` — 이건 OpenAI 비용이지 Oracle 과금이 아님)
- 키 없이 진단·예측·그래프·이식후보까지는 캡처 가능. 처방문/챗봇 텍스트만 키 필요.

## 데이터 출처
`Data/Prescription/` 의 `ontology.json` · `shadow_profile.json` · `programs.json` · `evidence.json`
(원래 이 파일들을 ADB에 적재해 쓰던 것. 로컬 모드는 같은 파일을 직접 읽음)
