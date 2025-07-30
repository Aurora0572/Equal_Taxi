from fastapi import APIRouter, Query, HTTPException
from fastapi_cache.decorator import cache
from ..services.seoul_api import fetch_best_100_destinations
from ..services.tmap_api import get_tmap_travel_time
from ..constants import DEFAULT_DATE
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/best_destinations")
@cache(expire=300)
async def get_best_destinations(
    sDate: str = DEFAULT_DATE[:-2] + "01",
    start_lng: float = Query(126.9784),
    start_lat: float = Query(37.5667),
):
    """
    인기 목적지와 ETA 반환
    """
    try:
        df = await fetch_best_100_destinations(sDate)
        top_places = df[["장소명", "이용건수"]].sort_values(
            by="이용건수", ascending=False
        ).head(10)

        results = []
        for row in top_places.to_dict(orient="records"):
            try:
                eta_sec = await get_tmap_travel_time(
                    start_lng, start_lat, start_lng + 0.01, start_lat + 0.01
                )
                row["estimated_seconds"] = eta_sec
                row["estimated_minutes"] = round(eta_sec / 60, 1)
            except Exception as e:
                logger.warning(f"ETA 계산 실패: {e}")
                row["estimated_seconds"] = None
                row["estimated_minutes"] = None
            results.append(row)

        return {"start_date": sDate, "top_destinations": results}
    except Exception as e:
        logger.exception("베스트 목적지 API 처리 중 오류")
        raise HTTPException(status_code=500, detail=str(e))
