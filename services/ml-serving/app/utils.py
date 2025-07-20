from __future__ import annotations

import joblib
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, Any

# 모델, 인코더 로딩 -------------------------------------------------------------

def _model_dir() -> Path:
    # 현재 파일 기준 상대 경로
    return Path(__file__).resolve().parent / "model"


def load_model_assets() -> Tuple[Any, Any, Any]:
    """
    model.pkl, le_loc.pkl, le_weather.pkl 로드.
    반환: (model, le_loc, le_weather)
    """
    mdir = _model_dir()
    model = joblib.load(mdir / "model.pkl")
    le_loc = joblib.load(mdir / "le_loc.pkl")
    le_weather = joblib.load(mdir / "le_weather.pkl")
    return model, le_loc, le_weather


# 예측 유틸 ---------------------------------------------------------------------

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
    """
    SmartDispatchAlgorithm 쪽에서 사용할 수 있도록
    request_dict 기반으로 대기시간을 예측해 준다.

    request_dict 예상 키:
      pickup_location -> 위치
      weather -> 날씨
      wheelchair -> 휠체어YN
      (선택) hour -> 시간대 (없으면 default_hour 또는 현재 시각)
      (선택) num_vehicles -> 해당지역운행차량수
      (선택) num_users -> 해당지역이용자수
    """
    from datetime import datetime

    # 시간대 결정
    hour = request_dict.get("hour")
    if hour is None:
        if default_hour is not None:
            hour = default_hour
        else:
            hour = datetime.now().hour

    loc = request_dict.get("pickup_location")
    weather = request_dict.get("weather", "맑음")
    wheelchair_yn = 1 if request_dict.get("wheelchair", False) else 0

    num_vehicles = request_dict.get("num_vehicles", default_vehicle_count)
    num_users = request_dict.get("num_users", default_user_count)

    try:
        loc_encoded = int(le_loc.transform([loc])[0])
        weather_encoded = int(le_weather.transform([weather])[0])
    except Exception:
        # 인코딩 실패 시 큰 값 반환 → 긴 대기시간으로 간주
        return 999.0

    df = build_predict_dataframe(
        hour,
        loc_encoded,
        weather_encoded,
        wheelchair_yn,
        num_vehicles,
        num_users,
    )
    pred = model.predict(df)[0]
    return float(pred)
