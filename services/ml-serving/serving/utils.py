from __future__ import annotations

import joblib
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, Any


# ------------------------------------------------------------------------------
# ✅ 모델, 인코더 경로 및 로딩 유틸
# ------------------------------------------------------------------------------

def _model_dir() -> Path:
    """
    모델 파일들이 저장된 디렉토리 반환
    현재 파일 기준으로 app/model 경로를 찾아감
    """
    return Path(__file__).resolve().parents[1] / "app" / "model"


def load_model_assets() -> Tuple[Any, Any, Any]:
    """
    저장된 모델 및 인코더(pkl)들을 메모리로 로드
    - model.pkl: 학습된 XGBoost 모델
    - le_loc.pkl: 위치 라벨 인코더
    - le_weather.pkl: 날씨 라벨 인코더
    반환값: (model, le_loc, le_weather)
    """
    mdir = _model_dir()
    model = joblib.load(mdir / "model.pkl")
    le_loc = joblib.load(mdir / "le_loc.pkl")
    le_weather = joblib.load(mdir / "le_weather.pkl")
    return model, le_loc, le_weather


# ------------------------------------------------------------------------------
# ✅ 예측 관련 함수
# ------------------------------------------------------------------------------

def build_predict_dataframe(
    시간대: int,
    loc_encoded: int,
    weather_encoded: int,
    휠체어YN: int,
    해당지역운행차량수: int,
    해당지역이용자수: int,
) -> pd.DataFrame:
    """
    예측에 사용할 입력값을 DataFrame 형식으로 구성
    입력 컬럼은 학습 시 사용한 피처들과 동일해야 함
    """
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
    입력된 요청(request_dict)을 기반으로 예측 대기시간(분)을 반환
    - 모델에 맞는 포맷으로 변환 후 예측 수행
    - 위치, 날씨 인코딩이 실패할 경우 예외 처리 후 999 반환
    """
    from datetime import datetime

    # 시간대 추출 (기본값은 현재 시각)
    hour = request_dict.get("hour")
    if hour is None:
        hour = default_hour if default_hour is not None else datetime.now().hour

    # 개별 피처 추출
    loc = request_dict.get("pickup_location")
    weather = request_dict.get("weather", "맑음")
    wheelchair_yn = 1 if request_dict.get("wheelchair", False) else 0
    num_vehicles = request_dict.get("num_vehicles", default_vehicle_count)
    num_users = request_dict.get("num_users", default_user_count)

    # 인코딩 처리 (에러 발생 시 fallback 값 반환)
    try:
        loc_encoded = int(le_loc.transform([loc])[0])
        weather_encoded = int(le_weather.transform([weather])[0])
    except Exception:
        return 999.0  # 인코딩 실패 시 매우 긴 대기시간 반환

    # 예측용 데이터프레임 생성 후 모델 예측 수행
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


# ------------------------------------------------------------------------------
# ✅ DispatchRequest 객체 → ML 입력값 추출 함수
# ------------------------------------------------------------------------------

def extract_features(request) -> list:
    """
    DispatchRequest 객체 기반으로 ML 예측에 필요한 피처 리스트 추출
    - 추출된 리스트는 [시간대, 위치코드, 날씨코드, 휠체어YN, 차량수, 이용자수] 순
    """
    from datetime import datetime
    print("🧪 extract_features 호출됨")  # 디버깅 로그

    # 시간대 파싱 (예외 발생 시 현재 시간 사용)
    try:
        hour = request.request_time.hour
    except:
        hour = datetime.now().hour

    # 기타 피처 추출
    loc = request.call_request.pickup_location
    weather = request.weather
    wheelchair_yn = 1 if request.call_request.wheelchair else 0
    num_vehicles = len(request.available_drivers)
    num_users = 20  # 실제 구현에서는 외부 데이터와 연동 가능

    # 인코딩 처리
    try:
        loc_encoded = int(request.le_loc.transform([loc])[0])
        weather_encoded = int(request.le_weather.transform([weather])[0])
    except Exception:
        print("⚠️ 위치 또는 날씨 인코딩 실패")
        return [hour, -1, -1, wheelchair_yn, num_vehicles, num_users]

    return [hour, loc_encoded, weather_encoded, wheelchair_yn, num_vehicles, num_users]