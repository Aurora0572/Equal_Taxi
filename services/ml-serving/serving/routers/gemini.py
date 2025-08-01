from fastapi import APIRouter, HTTPException
import google.generativeai as genai
from ..core.gemini_service import ask_gemini_model         # ✅ 수정
from ..core.ml_model      import load_model_assets, predict_waiting_time_from_request
from ..core.seoul_api     import fetch_daily_usage_data
from ..core.tmap_api      import get_tmap_travel_time
router = APIRouter()

# ML 모델 로드 (서버 시작 시 1회)
model, le_loc, le_weather = load_model_assets()

@router.post("/ask_gemini")
async def ask_gemini(prompt: str):
    """
    Gemini 모델 + ML 예측 결합 응답
    """
    try:
        # 1. ML 모델로 예측 (현재는 고정 입력, 추후 확장 가능)
        request_dict = {
            "pickup_location": "강남",
            "weather": "맑음",
            "wheelchair": False,
        }
        predicted_wait = predict_waiting_time_from_request(
            model, le_loc, le_weather, request_dict
        )

        # 2. Gemini에 보낼 프롬프트 생성
        full_prompt = (
            f"예상 배차 대기시간은 {predicted_wait:.1f}분입니다.\n"
            f"사용자 질문: {prompt}\n"
            "이 예측값을 고려해서 사용자에게 친절하고 이해하기 쉽게 설명해 주세요."
        )

        gen_model = genai.GenerativeModel("gemini-2.5-pro")
        response = gen_model.generate_content(full_prompt)

        return {
            "prompt": prompt,
            "predicted_waiting_time": predicted_wait,
            "response": response.text,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")
