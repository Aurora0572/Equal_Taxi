from __future__ import annotations

from fastapi import FastAPI, HTTPException
import pandas as pd

from .schemas import InputData
from .utils import load_model_assets, build_predict_dataframe
from .dispatch import router as dispatch_router  # 스마트 배차 라우터 포함


# FastAPI 앱 --------------------------------------------------------------------
app = FastAPI(
    title="스마트 장애인 콜택시 시스템",
    description="대기시간 예측 + 스마트 배차 API",
    version="2.0",
)

# 스마트 배차 라우터 추가
app.include_router(dispatch_router)

# 모델 로드 (프로세스 시작 시 1회)
model, le_loc, le_weather = load_model_assets()


# 루트 --------------------------------------------------------------------------
@app.get("/")
def read_root():
    return {
        "service": "스마트 장애인 콜택시 배차 시스템 v2.0",
        "endpoints": [
            "/predict/        - 대기시간 예측",
            "/smart_dispatch/ - 스마트 배차",
            "/batch_optimize/ - 다중 요청 전역 최적화",
            "/system_status/  - 시스템 상태",
            "/update_profile/ - 사용자 프로필 업데이트",
        ],
    }


# 예측 API ----------------------------------------------------------------------
@app.post("/predict/")
def predict(data: InputData):
    # 인코딩
    try:
        loc_encoded = int(le_loc.transform([data.위치])[0])
        weather_encoded = int(le_weather.transform([data.날씨])[0])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"알 수 없는 위치 또는 날씨입니다: {e}")

    df = build_predict_dataframe(
        data.시간대,
        loc_encoded,
        weather_encoded,
        data.휠체어YN,
        data.해당지역운행차량수,
        data.해당지역이용자수,
    )

    pred = model.predict(df)[0]
    return {"예상대기시간(분)": round(float(pred), 2)}
