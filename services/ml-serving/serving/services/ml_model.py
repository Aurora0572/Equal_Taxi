from __future__ import annotations
import joblib
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Tuple
from ..utils import model_dir
from .public_api import estimate_usage_stats

# 모델 로드
def load_model_assets() -> Tuple[Any, Any, Any]:
    mdir = model_dir()
    model = joblib.load(mdir / "model.pkl")
    le_loc = joblib.load(mdir / "le_loc.pkl")
    le_weather = joblib.load(mdir / "le_weather.pkl")
    return model, le_loc, le_weather

# 예측용 데이터프레임 생성
def build_predict_dataframe(
    시간대: int,
    loc_encoded: int,
    weather_encoded: int,
    휠체어YN: int,
    해당지역운행차량수: int,
    해당지역이용자수: int,
) -> pd.DataFrame:
    return pd.DataFrame(
        [[시간대, loc_encoded, weather_encoded, 휠체어YN, 해당지역운행차량수, 해당지역이용자수]],
        columns=['시간대', '위치_encoded', '날씨_encoded', '휠체어YN', '해당지역운행차량수', '해당지역이용자수']
    )

# 요청 기반 예측
def predict_waiting_time_from_request(
    model,
    le_loc,
    le_weather,
    request_dict: Dict[str, Any],
    *,
    default_hour: int = None,
    default_vehicle_count: int = 10,
    default_user_count: int = 20,
) -> float:
    hour = request_dict.get("hour") or default_hour or datetime.now().hour
    loc = request_dict.get("pickup_location")
    weather = request_dict.get("weather", "맑음")
    wheelchair_yn = 1 if request_dict.get("wheelchair", False) else 0

    try:
        est_vehicles, est_users = estimate_usage_stats(loc)
    except:
        est_vehicles, est_users = default_vehicle_count, default_user_count

    num_vehicles = request_dict.get("num_vehicles", est_vehicles)
    num_users = request_dict.get("num_users", est_users)

    try:
        loc_encoded = int(le_loc.transform([loc])[0])
        weather_encoded = int(le_weather.transform([weather])[0])
    except Exception:
        return 999.0

    df = build_predict_dataframe(
        hour, loc_encoded, weather_encoded, wheelchair_yn,
        num_vehicles, num_users,
    )
    pred = model.predict(df)[0]
    return float(pred)

# DispatchRequest 객체 기반 피처 추출
def extract_features(request) -> list:
    try:
        hour = request.request_time.hour
    except:
        hour = datetime.now().hour

    loc = request.call_request.pickup_location
    weather = request.weather
    wheelchair_yn = 1 if request.call_request.wheelchair else 0
    num_vehicles = len(request.available_drivers)
    num_users = 20

    try:
        loc_encoded = int(request.le_loc.transform([loc])[0])
        weather_encoded = int(request.le_weather.transform([weather])[0])
    except Exception:
        return [hour, -1, -1, wheelchair_yn, num_vehicles, num_users]

    return [hour, loc_encoded, weather_encoded, wheelchair_yn, num_vehicles, num_users]
