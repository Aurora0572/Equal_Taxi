from fastapi import FastAPI, HTTPException
from .dispatch import router as dispatch_router
from .utils import load_model_assets
from .schemas import InputData  # 예측 API 등에 필요 시 사용
from .utils import build_predict_dataframe  # 필요 시 사용

# ✅ FastAPI 앱 객체 생성 (ASGI 앱)
app = FastAPI(
    title="스마트 장애인 콜택시 시스템",
    description="대기시간 예측 + 스마트 배차 API",
    version="2.0",
)

# ✅ dispatch.py의 API 라우터 포함
app.include_router(dispatch_router)

# ✅ 모델 자산 로드 (예측 등에 필요)
model, le_loc, le_weather = load_model_assets()

# ✅ 루트 경로 확인용
@app.get("/")
def root():
    return {
        "message": "🚕 스마트 장애인 콜택시 API 서버 동작 중입니다.",
        "endpoints": [
            "/smart_dispatch/",
            "/batch_optimize/",
            "/system_status/",
            "/update_profile/",
        ]
    }