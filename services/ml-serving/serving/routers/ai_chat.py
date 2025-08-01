# serving/routers/ai_chat.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Body, HTTPException

# ── 내부 서비스 ──────────────────────────────────────
from ..core.gemini_service import ask_gemini_model
from ..core.seoul_api   import fetch_daily_usage_data
from ..core.tmap_api    import get_tmap_travel_time
from ..core.ml_model    import load_model_assets, predict_waiting_time_from_request
from ..routers.mock     import realtime_mock

import uuid

router = APIRouter()

model, le_loc, le_weather = load_model_assets()
chat_histories: Dict[str, List[Dict[str, str]]] = {}


@router.post("/ai/chat")
async def ai_chat(
    session_id: str | None = Body(None, description="대화 세션 ID(생략 시 자동 생성)"),
    prompt: str     = Body(..., description="사용자 질문(서울시장애인콜택시)")
):
    """
    mock 실시간 + 서울시 통계 + Tmap ETA + ML ETA를 종합해
    히스토리를 유지하며 답변을 생성한다.
    (우선배차·priority 문구는 제외)
    """
    try:
        # ── 히스토리 ─────────────────────────────
        history = chat_histories.get(session_id, [])

        # ── mock 실시간 데이터 ───────────────────
        mock = await realtime_mock()
        calls         = mock["calls"]
        waiting_users = mock["waiting_users"]
        mock_eta      = mock["mock_eta_minutes"]

        # ── 서울시 일 통계 ───────────────────────
        try:
            today = datetime.now().strftime("%Y%m%d")
            df = await fetch_daily_usage_data(today)
            total_requests  = int(df["접수건"].sum())
            avg_waiting_api = round(df["평균대기시간"].mean(), 1)
        except Exception:
            total_requests, avg_waiting_api = 1000, 15.0

        # ── Tmap ETA ────────────────────────────
        try:
            eta_sec  = await get_tmap_travel_time(126.9784, 37.5667,
                                                  126.984,  37.5000)
            tmap_eta = round(eta_sec / 60, 1)
        except Exception:
            tmap_eta = 12.0

        # ── ML ETA ──────────────────────────────
        req_dict = {"pickup_location": "강남", "weather": "맑음", "wheelchair": False}
        ml_eta   = predict_waiting_time_from_request(model, le_loc, le_weather, req_dict)

        fused_eta = round((mock_eta*0.5 + ml_eta*0.3 + tmap_eta*0.2), 1)

        # ── 히스토리 문자열 ──────────────────────
        history_txt = "\n".join(f"사용자: {h['user']}\nAI: {h['ai']}" for h in history)

        # ── Gemini 프롬프트 ─────────────────────
        full_prompt = f"""
이전 대화:
{history_txt}

새 질문: {prompt}

실시간/통계 데이터:
- 실시간 호출 {calls}건, 대기자 {waiting_users}명
- mock ETA: {mock_eta}분
- ML ETA  : {ml_eta:.1f}분
- Tmap ETA: {tmap_eta}분
- 통합 ETA: {fused_eta}분

위 정보를 참고해 친절하고 이해하기 쉬운 한국어 답변을 제공하세요.
"""

        answer = await ask_gemini_model(full_prompt)

        # ── 히스토리 저장 (최근 5개) ──────────────
        history.append({"user": prompt, "ai": answer})
        chat_histories[session_id] = history[-5:]

        # ── 응답 ────────────────────────────────
        return {
            "timestamp"      : datetime.now().isoformat(),
            "session_id"     : session_id,
            "answer"         : answer,
            "fused_eta"      : fused_eta,
            "mock_eta"       : mock_eta,
            "ml_eta"         : round(ml_eta, 1),
            "tmap_eta"       : tmap_eta,
            "total_requests" : total_requests,
            "avg_waiting_api": avg_waiting_api,
            "history_length" : len(chat_histories[session_id]),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI chat error: {e}")
