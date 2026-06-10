# -*- coding: utf-8 -*-
"""
SHADOW 처방 생성 — 그래프 입력 JSON → OpenAI → 처방문(①~⑤).

흐름:
  build_prescription_input.py 가 만든  처방입력_<자치구>.json  을 읽어
  '계산은 그래프, 글쓰기만 LLM' 원칙대로 OpenAI에 던지고 처방문을 받는다.
  LLM은 입력에 있는 제도·논문만 인용한다 (환각 차단).

준비:
  1) pip 설치됨: openai
  2) 환경변수:  $env:OPENAI_API_KEY = "본인키"   (절대 코드에 박지 말 것)
  3) 먼저 입력 생성:  python build_prescription_input.py 노원구 Q1,Q4

실행(한글경로·콘솔깨짐 함정 회피):
  $env:PYTHONIOENCODING="utf-8"
  C:/Users/brotherweek/AppData/Local/Programs/Python/Python312/python.exe generate_prescription.py 노원구
  C:/.../python.exe generate_prescription.py 노원구 gpt-4.1   # 모델 바꾸고 싶을 때
"""
import json, sys, io, os

if hasattr(sys.stdout, "buffer") and (getattr(sys.stdout, "encoding", "") or "").lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = os.path.dirname(os.path.abspath(__file__))

# ── 모델 (품질 우선 기본값 gpt-4o, 인자로 교체 가능) ────────────
DEFAULT_MODEL = "gpt-4o"

SYSTEM_PROMPT = """\
너는 '서울 5060 남성 1인가구 고립' 문제의 복지 처방을 작성하는 정책 분석가다.
너의 일은 새로운 사실을 만드는 것이 아니라, [입력]에 주어진 재료만으로
설득력 있는 처방문을 쓰는 것이다.

[절대 규칙]
1. [입력]에 없는 제도·논문·통계·한계코드를 새로 만들지 마라. (지어내면 실패)
2. 한계·need·이식후보는 이미 계산되어 주어진다. 너는 재판단하지 말고 그대로 서술하라.
3. 논문(근거_논문)은 ②한계·③방향을 정당화할 때만 인용한다. ④⑤에 논문을 인용하지 마라.
4. ④의 근거는 '다른 지역의 실제 제도'(이식후보)다. 논문이 아니라 제도 이름·지역을 댄다.
5. 논문 인용 시 evidence_id가 아니라 (저자, 연도) 형태로 자연스럽게 녹여라.
6. 한국어. 행정 보고서 톤. 과장·감정 호소 금지, 근거(논문·통계·실제사례)로만 설득.
7. 이식후보가 없는 한계(예: 자치구귀속)는 외부 사례 없이 '서울 전역으로 확대' 같은 구조 개선으로 ④⑤를 서술하라.
8. [입력]의 '지역_프로파일'(quadrant·회피_주동인·의존_주동인·고위험_행정동)을 ①②⑤에 적극 활용해
   '왜 이 자치구가 위험한지'를 구체적 지표·동(洞) 이름으로 못박아라. (일반론 금지)

[출력 구조] — 반드시 ①~⑤ 순서, 각 항목 머리에 동그라미 번호
① 현행: 선택 자치구의 위험 맥락(회피_주동인·고위험_행정동)을 짧게 짚고, 지금 있는 관련 제도를 인정한다.
② 한계: 주어진 한계별로 "어떤 제도가 / 왜 부족한가"를 서술. 여기서 논문 인용. 자치구 프로파일과 연결.
③ 방향: 한계가 가리키는 need를 "그래서 ~한 방향의 제도가 필요하다"로 제시. 여기서 논문 인용.
④ 외부 레퍼런스: 이식후보 제도를 "이 방향은 [지역]의 [제도]에서 이미 검증됐다"로 제시.
                 reference_priority(해외>국내타지역>서울타자치구) 순으로 강도 표현.
⑤ 이식 제안: "따라서 [선택 자치구](특히 고위험 행정동)에도 ~한 제도가 마련돼야 한다"로 마무리.
"""

USER_TEMPLATE = """\
아래는 그래프가 계산한 [입력]이다. 이 재료만으로 ①~⑤ 처방문을 작성하라.

[입력]
{payload}
"""


def main():
    gu = sys.argv[1] if len(sys.argv) > 1 else "노원구"
    model = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL

    # 1) 키 확인
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ 환경변수 OPENAI_API_KEY 가 없습니다.")
        print('   PowerShell:  $env:OPENAI_API_KEY = "본인키"  설정 후 다시 실행하세요.')
        sys.exit(1)

    # 2) 입력 JSON 로드 (없으면 안내)
    in_path = os.path.join(BASE, f"처방입력_{gu}.json")
    if not os.path.exists(in_path):
        print(f"❌ 입력 파일이 없습니다: {in_path}")
        print(f"   먼저 실행:  python build_prescription_input.py {gu} Q1,Q4")
        sys.exit(1)
    payload = json.load(open(in_path, encoding="utf-8"))

    # 3) OpenAI 호출
    from openai import OpenAI
    client = OpenAI()  # 키는 환경변수에서 자동 로드
    print(f"[{gu}] 모델={model} 호출 중...")
    resp = client.chat.completions.create(
        model=model,
        temperature=0.4,  # 사실 기반 안정성 우선 (너무 창의적이면 환각 위험)
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(
                payload=json.dumps(payload, ensure_ascii=False, indent=2))},
        ],
    )
    text = resp.choices[0].message.content

    # 4) 저장 + 출력
    out_path = os.path.join(BASE, f"처방문_{gu}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# 처방문 — {gu} (모델: {model})\n\n{text}\n")
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)
    u = resp.usage
    print(f"\n토큰: in {u.prompt_tokens} / out {u.completion_tokens} / 합 {u.total_tokens}")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
