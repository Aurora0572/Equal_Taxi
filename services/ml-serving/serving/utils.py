from __future__ import annotations

import joblib
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, Any
from datetime import datetime

# 📌 추가: XLSX 오픈 API 호출용 함수 임포트
from .api import fetch_daily_usage_data
import httpx
from .constants import TMAP_API_KEY, TMAP_BASE_URL


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
# ✅ 오픈 API 기반 운행/수요 추정 함수
# ------------------------------------------------------------------------------

def estimate_usage_stats(location: str, date: str = None) -> Tuple[int, int]:
    """
    서울시 오픈 API 데이터를 통해 해당 위치의 운행 차량수 및 콜 수 추정
    """
    if not date:
        date = datetime.now().strftime("%Y%m%d")

    try:
        df = fetch_daily_usage_data(date)
        filtered = df[df["출발지"].astype(str).str.contains(location)]
        vehicle_count = int(filtered["운행건수"].sum())
        user_count = int(filtered["콜수"].sum())
        return vehicle_count, user_count
    except Exception as e:
        print("❌ estimate_usage_stats 오류:", str(e))
        return 10, 20  # 기본 fallback


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
    - 오픈 API에서 지역별 수요/공급 데이터를 자동으로 추정해 반영
    """
    # 시간대 추출 (기본값은 현재 시각)
    hour = request_dict.get("hour")
    if hour is None:
        hour = default_hour if default_hour is not None else datetime.now().hour

    # 개별 피처 추출
    loc = request_dict.get("pickup_location")
    weather = request_dict.get("weather", "맑음")
    wheelchair_yn = 1 if request_dict.get("wheelchair", False) else 0

    # 오픈 API로 지역 기반 통계 추정
    try:
        est_vehicles, est_users = estimate_usage_stats(loc)
    except:
        est_vehicles, est_users = default_vehicle_count, default_user_count

    # 외부 주입값이 있으면 우선 적용
    num_vehicles = request_dict.get("num_vehicles", est_vehicles)
    num_users = request_dict.get("num_users", est_users)

    # 인코딩 처리
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
    print("🧪 extract_features 호출됨")

    try:
        hour = request.request_time.hour
    except:
        hour = datetime.now().hour

    loc = request.call_request.pickup_location
    weather = request.weather
    wheelchair_yn = 1 if request.call_request.wheelchair else 0
    num_vehicles = len(request.available_drivers)
    num_users = 20  # 또는 오픈 API 연동 가능

    try:
        loc_encoded = int(request.le_loc.transform([loc])[0])
        weather_encoded = int(request.le_weather.transform([weather])[0])
    except Exception:
        print("⚠️ 위치 또는 날씨 인코딩 실패")
        return [hour, -1, -1, wheelchair_yn, num_vehicles, num_users]

    return [hour, loc_encoded, weather_encoded, wheelchair_yn, num_vehicles, num_users]


async def get_public_transit_alternatives(
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float
) -> dict:
    """
    TMap API를 통해 대중교통 경로 대안을 조회합니다.
    
    Args:
        start_lat: 출발지 위도
        start_lng: 출발지 경도
        end_lat: 도착지 위도
        end_lng: 도착지 경도
    
    Returns:
        dict: 대중교통 경로 정보
    """
    url = f"{TMAP_BASE_URL}/routes/transit"
    
    headers = {
        "Accept": "application/json",
        "appKey": TMAP_API_KEY
    }
    
    params = {
        "startX": str(start_lng),
        "startY": str(start_lat),
        "endX": str(end_lng),
        "endY": str(end_lat),
        "format": "json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"TMap API 호출 실패: {e}")
        return None
