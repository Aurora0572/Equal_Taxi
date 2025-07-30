import logging
import os
import pandas as pd
from datetime import datetime
from httpx import AsyncClient
from fastapi import HTTPException
from ..constants import TMAP_API_KEY, TMAP_BASE_URL

logger = logging.getLogger(__name__)

# 서울시 오픈 API 데이터 기반 추정
def estimate_usage_stats(location: str, date: str = None) -> tuple[int, int]:
    if not date:
        date = datetime.now().strftime("%Y%m%d")
    try:
        df = fetch_daily_usage_data_sync(date)
        filtered = df[df["출발지"].astype(str).str.contains(location)]
        vehicle_count = int(filtered["운행건수"].sum())
        user_count = int(filtered["콜수"].sum())
        return vehicle_count, user_count
    except Exception as e:
        logger.warning(f"estimate_usage_stats 오류: {e}")
        return 10, 20

# 동기 방식으로 데이터 로드 (ML 예측용)
def fetch_daily_usage_data_sync(date: str) -> pd.DataFrame:
    import requests
    url = "http://m.calltaxi.sisul.or.kr/api/open/newEXCEL0001.asp"
    params = {"key": os.getenv("CALLTAXI_USAGE_KEY"), "eDate": date}
    r = requests.get(url, params=params)
    r.encoding = 'euc-kr'
    tables = pd.read_html(r.text, encoding='euc-kr')
    return tables[0]

# 비동기 방식 (FastAPI API용)
async def fetch_daily_usage_data(date: str) -> pd.DataFrame:
    url = "http://m.calltaxi.sisul.or.kr/api/open/newEXCEL0001.asp"
    params = {"key": os.getenv("CALLTAXI_USAGE_KEY"), "eDate": date}
    try:
        async with AsyncClient() as client:
            response = await client.get(url, params=params)
            response.encoding = 'euc-kr'
            tables = pd.read_html(response.text, encoding='euc-kr')
            if not tables:
                raise ValueError("No tables found in response")
            return tables[0]
    except Exception as e:
        logger.error(f"데이터 가져오기 실패: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 가져오기 실패: {str(e)}")

# Tmap 대중교통 API
async def get_public_transit_alternatives(
    start_lat: float, start_lng: float, end_lat: float, end_lng: float
) -> dict:
    url = f"{TMAP_BASE_URL}/routes/transit"
    headers = {"Accept": "application/json", "appKey": TMAP_API_KEY}
    params = {
        "startX": str(start_lng),
        "startY": str(start_lat),
        "endX": str(end_lng),
        "endY": str(end_lat),
        "format": "json"
    }
    try:
        async with AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"TMap API 호출 실패: {e}")
        return None
