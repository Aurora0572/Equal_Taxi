from fastapi import APIRouter
from datetime import datetime
import random

router = APIRouter()

def get_time_multiplier(hour: int, weekday: int) -> float:
    """
    시간대 및 요일에 따른 multiplier 계산
    weekday: 월(0) ~ 일(6)
    """
    multiplier = 1.0

    # 심야 시간 (0~5시): 콜/차량 수 절반
    if 0 <= hour < 6:
        multiplier *= 0.5

    # 출근 시간 (7~9시): 수요 2배
    if 7 <= hour < 10:
        multiplier *= 2.0

    # 퇴근 시간 (17~20시): 수요 2.5배
    if 17 <= hour < 21:
        multiplier *= 2.5

    # 주말(토, 일): 전체적으로 1.5배
    if weekday >= 5:
        multiplier *= 1.5

    return multiplier

@router.get("/realtime")
async def realtime_mock():
    """
    시간대/요일 패턴 기반의 mock 실시간 데이터 생성
    """
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()

    # 기준 값
    base_calls = 2000 / 24  # 시간당 약 83콜
    base_cars = 600 / 24    # 시간당 약 25대 활동
    base_waiting = 300 / 24 # 시간당 평균 12~13명 대기

    multiplier = get_time_multiplier(hour, weekday)

    # 호출량/차량/대기자 수 계산 + ±10% 랜덤 변동
    calls = int(base_calls * multiplier * (1 + random.uniform(-0.1, 0.1)))
    active_cars = int(base_cars * multiplier * (1 + random.uniform(-0.1, 0.1)))
    waiting_users = int(base_waiting * multiplier * (1 + random.uniform(-0.1, 0.1)))

    # 최소 1 이상으로 보장
    calls = max(calls, 1)
    active_cars = max(active_cars, 1)
    waiting_users = max(waiting_users, 1)

    return {
        "timestamp": now.isoformat(),
        "hour": hour,
        "weekday": weekday,
        "calls": calls,
        "active_cars": active_cars,
        "waiting_users": waiting_users
    }
