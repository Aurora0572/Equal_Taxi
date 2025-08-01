import math
import logging
import asyncio
import re
from fastapi import APIRouter
from ..routers.mock import realtime_mock
from ..schemas import UsageV2Response, MockRealtimeResponse
from ..core.gemini_service import ask_gemini_model 
from ..core.seoul_api   import fetch_daily_usage_data      # ✅ 수정
from ..core.tmap_api    import get_tmap_travel_time   
from ..core.ml_model import load_model_assets

logger = logging.getLogger(__name__)
router = APIRouter()

model, le_loc, le_weather = load_model_assets()

@router.get("/usage", response_model=UsageV2Response)
async def get_usage():
    """
    /v2/usage
    - 서울시 통계 + Tmap ETA
    - mock 실시간 데이터 + priority_score(log 보정)
    - Gemini 코멘트 + Gemini ETA (통계 + Tmap + mock 기반)
    - priority_score 계산 시 Gemini ETA까지 반영
    """
    try:
        # 1. 서울시 API 데이터
        date = "20250131"
        df = await fetch_daily_usage_data(date)

        # Tmap ETA 계산
        top_locations_series = df.groupby("기준일")["탑승건"].sum().nlargest(10)
        top_locations = {}

        async def calc_eta_for_location(k: str, v: int):
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

        await asyncio.gather(
            *(calc_eta_for_location(k, v) for k, v in top_locations_series.items())
        )

        # 평균 ETA (Tmap 기반)
        eta_list = [loc["estimated_minutes"] for loc in top_locations.values()
                    if loc["estimated_minutes"] is not None]
        avg_eta_minutes = sum(eta_list) / len(eta_list) if eta_list else 0

        # 2. mock 데이터
        mock_data = await realtime_mock()
        calls = mock_data.get("calls", 1)
        active_cars = mock_data.get("active_cars", 1)
        waiting_users = mock_data.get("waiting_users", 0)

        # 3. Gemini 프롬프트
        gemini_eta_prompt = f"""
        다음 데이터를 종합해서 예상 배차 시간을 (분 단위 숫자만) 예측해줘.
        - 총 요청 건수: {int(df['접수건'].sum())}
        - 평균 대기 시간(서울시 API): {df['평균대기시간'].mean():.1f}분
        - Tmap ETA: {avg_eta_minutes:.1f}분
        - 현재 호출 건수: {calls}
        - 대기자 수: {waiting_users}
        - 운행 차량 수: {active_cars}
        결과는 숫자만 출력 (예: 25.4)
        """

        gemini_comment_prompt = (
            f"현재 호출 {calls}건, 대기자 {waiting_users}명, 차량 {active_cars}대, "
            f"평균 ETA {avg_eta_minutes:.1f}분. "
            "배차 긴급도와 교통 상황을 1~2문장으로 한국어로 요약해줘."
        )

        gemini_eta_task = asyncio.create_task(ask_gemini_model(gemini_eta_prompt))
        gemini_comment_task = asyncio.create_task(ask_gemini_model(gemini_comment_prompt))

        # Gemini ETA
        gemini_eta = None
        try:
            gemini_eta_text = await gemini_eta_task
            match = re.search(r"(\d+(\.\d+)?)", gemini_eta_text)
            if match:
                gemini_eta = float(match.group(1))
        except Exception as e:
            logger.warning(f"Gemini ETA 예측 실패: {e}")

        # Gemini 코멘트
        gemini_comment = ""
        try:
            gemini_comment = await gemini_comment_task
        except Exception as e:
            logger.warning(f"Gemini 코멘트 생성 실패: {e}")

        # 4. priority_score 계산 (Gemini ETA 반영)
        demand = calls + waiting_users
        supply = max(active_cars, 1)
        base_ratio = demand / supply

        # Gemini ETA가 있으면 평균 ETA로 사용
        effective_eta = avg_eta_minutes
        if gemini_eta is not None:
            effective_eta = (avg_eta_minutes + gemini_eta) / 2

        traffic_factor = 1 + (math.log1p(effective_eta) / 3)
        final_ratio = math.log1p(base_ratio) * traffic_factor

        capped_ratio = min(final_ratio, 5.0)
        weighted_score = 50 + (capped_ratio * 20)
        raw_score = min(weighted_score, 100.0)

        normalized = raw_score / 100.0
        priority_score = round(0.3 + 0.7 * normalized, 3)

        # 5. 최종 응답
        return UsageV2Response(
            endpoint="/v2/usage",
            total_requests=int(df["접수건"].sum()),
            status="ok",
            estimated_minutes=round(avg_eta_minutes, 1) if avg_eta_minutes else None,
            gemini_eta=gemini_eta,
            gemini_comment=gemini_comment,
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