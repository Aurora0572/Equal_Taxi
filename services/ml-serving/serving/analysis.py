from datetime import datetime
import pandas as pd
from typing import Dict, List, Tuple
from .api import fetch_daily_usage_data
from .utils import get_public_transit_alternatives

async def analyze_dispatch_times(location: str, date: str = None) -> Dict:
    """
    특정 지역의 콜택시 배차 시간과 대중교통 시간을 비교 분석
    """
    if not date:
        date = datetime.now().strftime("%Y%m%d")
    
    # 1. 콜택시 데이터 가져오기
    df = await fetch_daily_usage_data(date)
    location_data = df[df["출발지"].str.contains(location)]
    
    # 2. 기본 통계 계산
    stats = {
        "평균_대기시간": float(location_data["평균대기시간"].mean()),
        "최소_대기시간": float(location_data["평균대기시간"].min()),
        "최대_대기시간": float(location_data["평균대기시간"].max()),
        "총_호출건수": int(location_data["접수건"].sum()),
        "성공_배차건수": int(location_data["탑승건"].sum())
    }
    
    # 3. 시간대별 분석
    hourly_stats = location_data.groupby("시간대").agg({
        "평균대기시간": "mean",
        "접수건": "sum",
        "탑승건": "sum"
    }).to_dict()
    
    return {
        "위치": location,
        "날짜": date,
        "기본통계": stats,
        "시간대별통계": hourly_stats
    }

async def compare_with_public_transit(
    start_location: str,
    end_location: str,
    start_coords: Tuple[float, float],
    end_coords: Tuple[float, float]
) -> Dict:
    """
    콜택시와 대중교통 소요시간 비교
    """
    # 1. 콜택시 평균 대기 + 이동시간
    taxi_analysis = await analyze_dispatch_times(start_location)
    avg_wait_time = taxi_analysis["기본통계"]["평균_대기시간"]
    
    # 2. 대중교통 경로 조회
    transit_info = await get_public_transit_alternatives(
        start_lat=start_coords[0],
        start_lng=start_coords[1],
        end_lat=end_coords[0],
        end_lng=end_coords[1]
    )
    
    return {
        "출발지": start_location,
        "도착지": end_location,
        "콜택시_예상시간": {
            "대기시간": avg_wait_time,
            "총소요시간": avg_wait_time + (transit_info.get("예상소요시간", 0) if transit_info else 0)
        },
        "대중교통_정보": transit_info
    }