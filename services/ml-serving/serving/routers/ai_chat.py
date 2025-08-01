from fastapi import APIRouter, HTTPException, Body
from datetime import datetime
from typing import Dict, List

from ..core.gemini_service import ask_gemini_model
from serving.core.seoul_api import fetch_daily_usage_data
from serving.core.tmap_api import get_tmap_travel_time
from serving.core.ml_model import load_model_assets, predict_waiting_time_from_request

router = APIRouter()

# 모델 로드 (서버 시작 시 1회)
model, le_loc, le_weather = load_model_assets()

# 세션별 대화 히스토리 저장소 (메모리 기반)
chat_histories: Dict[str, List[Dict[str, str]]] = {}


@router.post("/ai/chat")
async def ai_chat(
    session_id: str = Body(..., description="대화 세션 ID"),
    prompt: str = Body(..., description="서울시장애인콜택시 관련 질문")
):
    """
    히스토리 기반 AI 채팅:
    - 같은 session_id 안에서 문맥을 유지
    - 서울시 API, Tmap ETA, ML 모델을 종합해 답변
    """
    try:
        # 1. 현재 세션의 히스토리 가져오기 (없으면 새로)
        history = chat_histories.get(session_id, [])

        # 2. 서울시 API 데이터 (금일)
        try:
            date = datetime.now().strftime("%Y%m%d")
            df = await fetch_daily_usage_data(date)
            total_requests = int(df["접수건"].sum())
            avg_waiting_time = round(df["평균대기시간"].mean(), 1)
        except Exception:
            total_requests = 1000
            avg_waiting_time = 15.0

        # 3. Tmap ETA (서울시청 기준)
        try:
            eta_seconds = await get_tmap_travel_time(
                126.9784, 37.5667,
                126.9784 + 0.01, 37.5667 + 0.01
            )
            tmap_eta = round(eta_seconds / 60, 1)
        except Exception:
            tmap_eta = 12.0

        # 4. ML 모델 예측
        request_dict = {
            "pickup_location": "강남",
            "weather": "맑음",
            "wheelchair": False,
        }
        predicted_wait = predict_waiting_time_from_request(
            model, le_loc, le_weather, request_dict
        )

        # 5. 대화 히스토리 텍스트 생성
        history_text = "\n".join(
            [f"사용자: {h['user']}\nAI: {h['ai']}" for h in history]
        )

        # 6. Gemini 프롬프트 (히스토리 포함)
        full_prompt = f"""
다음은 사용자와 AI의 이전 대화 기록입니다:
{history_text}

새로운 사용자 질문: {prompt}

참고할 데이터:
- 오늘 총 호출 건수: {total_requests}
- 서울시 평균 대기시간: {avg_waiting_time}분
- Tmap ETA: {tmap_eta}분
- ML 모델 ETA: {predicted_wait:.1f}분

이 문맥을 바탕으로 자연스럽게 이어서 답변하세요.
"""

        gemini_response = await ask_gemini_model(full_prompt)

        # 7. 히스토리 갱신 (최근 5개만 저장)
        history.append({"user": prompt, "ai": gemini_response})
        chat_histories[session_id] = history[-5:]

        # 8. 응답 반환
        return {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "answer": gemini_response,
            "history_length": len(chat_histories[session_id]),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI chat error: {e}")
