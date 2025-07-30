import math
import logging
from fastapi import APIRouter
from ..routers.mock import realtime_mock
from ..schemas import UsageV2Response, MockRealtimeResponse
from ..services.seoul_api import fetch_daily_usage_data
from ..services.tmap_api import get_tmap_travel_time
from ..services.ml_model import load_model_assets

logger = logging.getLogger(__name__)
router = APIRouter()

# 모델 자산 로딩 (서버 시작 시 1회)
model, le_loc, le_weather = load_model_assets()

@router.get("/v2/usage", response_model=UsageV2Response)
async def get_usage():
    """
    /v2/usage
    실제 usage 데이터 + mock 실시간 데이터 + priority_score(교통상황 + 로그 보정)
    """
    try:
        # 1. 실제 usage 데이터
        date = "20250131"
        df = await fetch_daily_usage_data(date)

        # 상위 목적지 ETA 계산
        top_locations_series = df.groupby("기준일")["탑승건"].sum().nlargest(10)
        top_locations = {}
        for k, v in top_locations_series.items():
            try:
                eta_seconds = await get_tmap_travel_time(
                    126.9784, 37.5667,
                    126.9784 + 0.01, 37.5667 + 0.01
                )
                eta_minutes = round(eta_seconds / 60, 1)
            except Exception as e:
                logger.warning(f"ETA 계산 실패: {e}")
                eta_minutes = None
            top_locations[str(k)] = {
                "rides": int(v),
                "estimated_minutes": eta_minutes,
            }

        # ETA 평균
        eta_list = [loc["estimated_minutes"] for loc in top_locations.values() if loc["estimated_minutes"] is not None]
        avg_eta_minutes = sum(eta_list) / len(eta_list) if eta_list else 0

        # 2. mock 데이터
        mock_data = await realtime_mock()
        calls = mock_data.get("calls", 1)
        active_cars = mock_data.get("active_cars", 1)
        waiting_users = mock_data.get("waiting_users", 0)

        # 3. priority_score 계산 (로그 보정)
        demand = calls + waiting_users
        supply = max(active_cars, 1)
        base_ratio = demand / supply

        # 로그 보정으로 ETA 영향 완화
        traffic_factor = 1 + (math.log1p(avg_eta_minutes) / 3)
        final_ratio = base_ratio * traffic_factor

        # capped
        capped_ratio = min(final_ratio, 3.0)
        weighted_score = 50 + (capped_ratio * 20)
        raw_score = min(weighted_score, 100.0)

        # 0.3~1.0 정규화
        normalized = raw_score / 100.0
        priority_score = round(0.3 + 0.7 * normalized, 3)

        # 4. 응답
        return UsageV2Response(
            endpoint="/v2/usage",
            total_requests=int(df["접수건"].sum()),
            status="ok",
            mock_realtime=MockRealtimeResponse(
                calls=calls,
                active_cars=active_cars,
                waiting_users=waiting_users,
                priority_score=priority_score
            )
        )

    except Exception as e:
        logger.exception("Usage stats error")
        raise