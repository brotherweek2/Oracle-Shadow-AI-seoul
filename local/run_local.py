# -*- coding: utf-8 -*-
"""
run_local.py — 오프라인(로컬) 모드로 대시보드 실행.

SHADOW_LOCAL=1 을 켜고 streamlit 을 띄운다.
이러면 처방·챗봇·그래프가 ADB 없이 로컬 JSON 으로 동작한다.
(처방문/챗봇 '텍스트 생성'에는 OPENAI_API_KEY 가 .env 에 있어야 한다 — Oracle 과금 아님)

사용:
  python local/run_local.py
"""
import os
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

env = dict(os.environ)
env["SHADOW_LOCAL"] = "1"
env["PYTHONUTF8"] = "1"

cmd = [sys.executable, "-m", "streamlit", "run", "shadow_service.py"]
print("[local] SHADOW_LOCAL=1 로 대시보드 실행 (ADB 미사용)")
print("[local]", " ".join(cmd), "  (cwd:", ROOT, ")")
subprocess.run(cmd, cwd=ROOT, env=env)
