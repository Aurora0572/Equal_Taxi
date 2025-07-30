from fastapi import APIRouter, Query, HTTPException
from ..schemas import UsageResponse, UsageSummary
from ..services.seoul_api import fetch_daily_usage_data
from ..services.tmap_api import get_tmap_travel_time
from ..services.ml_model import load_model_assets, predict_waiting_time_from_request
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# 모델 자산 로딩 (서버 시작 시 1회만)
model, le_loc, le_weather = load_model_assets()

@router.get("/usage", response_model=UsageResponse)
async def get_usage_stats(
    date: str = "20250131",
    start_lng: float = Query(126.9784),
    start_lat: float = Query(37.5667),
):
    """
    이용 통계 + 각 상위 목적지 ETA + ML 기반 대기시간 예측
    """
    try:
        df = await fetch_daily_usage_data(date)

        # ----------------------------
        # ML 예측값 계산
        # ----------------------------
        request_dict = {
            "pickup_location": "서울역",  # 좌표를 기반으로 매핑할 수도 있음
            "weather": "맑음",
            "wheelchair": False,
        }
        predicted_waiting_time = predict_waiting_time_from_request(
            model, le_loc, le_weather, request_dict
        )

        # ----------------------------
        # 기존 통계 + ETA
        # ----------------------------
        top_locations_series = df.groupby("기준일")["탑승건"].sum().nlargest(10)
        top_locations = {}
        for k, v in top_locations_series.items():
            try:
                eta_seconds = await get_tmap_travel_time(
                    start_lng, start_lat, start_lng + 0.01, start_lat + 0.01
                )
                eta_minutes = round(eta_seconds / 60, 1)
            except Exception as e:
                logger.warning(f"ETA 계산 실패: {e}")
                eta_seconds, eta_minutes = None, None

            top_locations[str(k)] = {
                "rides": int(v),
                "estimated_seconds": eta_seconds,
                "estimated_minutes": eta_minutes,
            }

        summary = UsageSummary(
            date=date,
            total_requests=int(df["접수건"].sum()),
            total_rides=int(df["탑승건"].sum()),
            total_vehicles=int(df["차량운행"].sum()),
            avg_waiting_time=float(df["평균대기시간"].mean()),
            avg_fare=float(df["평균요금"].mean()),
            avg_distance=float(df["평균승차거리"].mean()),
            top_locations=top_locations,
        )

        # ML 예측값을 함께 응답
        return {
            "summary": summary,
            "predicted_waiting_time": predicted_waiting_time
        }

    except Exception as e:
        logger.exception("Usage stats error")
        raise HTTPException(status_code=500, detail=str(e))