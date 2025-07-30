from fastapi import APIRouter
from datetime import datetime, timedelta
import random
from typing import List, Dict, Any

router = APIRouter()

# ==========================================
# 시간대별 multiplier 계산
# ==========================================
def get_time_multiplier(hour: int, weekday: int) -> float:
    """
    시간대/요일에 따라 multiplier 반환
    """
    multiplier = 1.0

    # 심야 시간 (0~5시): 수요 적음
    if 0 <= hour < 6:
        multiplier *= 0.5

    # 출근 시간 (7~9시): 수요 증가
    if 7 <= hour < 10:
        multiplier *= 2.0

    # 퇴근 시간 (17~20시): 수요 증가
    if 17 <= hour < 21:
        multiplier *= 2.5

    # 주말 보정 (토=5, 일=6)
    if weekday >= 5:
        multiplier *= 1.3

    return multiplier

# ==========================================
# 페르소나 생성
# ==========================================
PERSONA_TYPES = [
    "중증보행장애인",
    "정신적 장애(단독 가능)",
    "정신적 장애(보호자 필요)",
    "국가유공자",
    "외국인 휠체어 사용자",
    "장기회원",
    "일시적 장애(의료진단서)"
]

def generate_personas(n: int = 200) -> List[Dict[str, Any]]:
    """
    랜덤 페르소나 200명 생성
    """
    now = datetime.now()
    personas = []
    for i in range(n):
        persona_type = random.choice(PERSONA_TYPES)
        wheelchair = "휠체어" in persona_type or persona_type == "중증보행장애인"
        wait_time = random.randint(1, 40)  # 분 단위
        distance_km = round(random.uniform(1, 15), 1)
        request_time = now - timedelta(minutes=wait_time)
        personas.append({
            "id": i + 1,
            "persona_type": persona_type,
            "wheelchair": wheelchair,
            "wait_time": wait_time,
            "distance_km": distance_km,
            "request_time": request_time.isoformat()
        })
    return personas

# ==========================================
# 점수 계산 유틸
# ==========================================
def normalize(value, min_val, max_val):
    """0~1 정규화"""
    if max_val == min_val:
        return 0.0
    return (value - min_val) / (max_val - min_val)

def compute_priority_scores(calls_detail: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    calls_detail: [{id, wait_time, distance_km, wheelchair, request_time, ...}]
    return: 우선순위 점수 추가한 정렬된 리스트
    """
    if not calls_detail:
        return []

    # request_time이 문자열일 수 있으므로 datetime 변환
    for c in calls_detail:
        if isinstance(c["request_time"], str):
            c["request_time"] = datetime.fromisoformat(c["request_time"])

    # 1. 정규화 기준값 구하기
    wait_times = [c["wait_time"] for c in calls_detail]
    distances = [c["distance_km"] for c in calls_detail]
    min_wait, max_wait = min(wait_times), max(wait_times)
    min_dist, max_dist = min(distances), max(distances)

    # 2. 요청 시간 빠른 순으로 정렬해서 rank 부여
    sorted_by_time = sorted(calls_detail, key=lambda x: x["request_time"])
    for idx, call in enumerate(sorted_by_time):
        call["order_rank"] = idx + 1

    min_rank, max_rank = 1, len(calls_detail)

    # 3. 점수 계산
    for call in calls_detail:
        # 선착순 점수 (빠른 요청일수록 1에 가까움)
        order_score = 1 - normalize(call["order_rank"], min_rank, max_rank)

        # 대기시간 점수 (길수록 1에 가까움)
        wait_score = normalize(call["wait_time"], min_wait, max_wait)

        # 거리 점수 (짧을수록 1에 가까움)
        distance_score = 1 - normalize(call["distance_km"], min_dist, max_dist)

        # 휠체어 점수
        wheelchair_score = 1.0 if call.get("wheelchair") else 0.0

        # 최종 점수 (비율 적용)
        call["priority_score"] = round(
            0.2 * order_score +
            0.3 * wait_score +
            0.3 * distance_score +
            0.2 * wheelchair_score,
            3
        )

    # 4. 점수 높은 순으로 정렬
    return sorted(calls_detail, key=lambda x: x["priority_score"], reverse=True)

# ==========================================
# 실시간 mock 데이터 API
# ==========================================
@router.get("/realtime")
async def realtime_mock():
    """
    시간대/요일 패턴 기반의 mock 실시간 데이터 생성
    하루 평균 이용자수 4000건을 기준으로 하고,
    호출 수(calls)는 최대 3500 이하로 제한.
    ETA는 기본 50~70분, 혼잡 시 1.5배 (최대 120분).
    """
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()

    # --- base 값 설정 ---
    base_calls = 4000 / 24    # 하루 4000건 → 시간당 약 167건
    base_cars = 2000 / 24     # 시간당 약 83대
    base_waiting = 800 / 24   # 시간당 약 33명 대기
    multiplier = get_time_multiplier(hour, weekday)

    # --- 실시간 콜/차량/대기자 수 ---
    calls = int(base_calls * multiplier * (1 + random.uniform(-0.1, 0.1)))
    active_cars = int(base_cars * multiplier * (1 + random.uniform(-0.1, 0.1)))
    waiting_users = int(base_waiting * multiplier * (1 + random.uniform(-0.1, 0.1)))

    # 상한/하한 보정
    calls = min(max(calls, 1), 3500)  # 3500 이상은 제한
    active_cars = max(active_cars, 1)
    waiting_users = max(waiting_users, 1)

    # --- ETA(평균 배차 시간) mock ---
    base_eta = random.uniform(50, 70)
    eta_multiplier = 1.0
    if 7 <= hour < 10 or 17 <= hour < 21:
        eta_multiplier = 1.5
    elif weekday >= 5 and 10 <= hour < 18:
        eta_multiplier = 1.2

    eta_minutes = round(min(base_eta * eta_multiplier, 120), 1)

    # --- 페르소나 기반 우선순위 계산 ---
    calls_detail = generate_personas(200)
    ranked_calls = compute_priority_scores(calls_detail)

    return {
        "timestamp": now.isoformat(),
        "hour": hour,
        "weekday": weekday,
        "calls": calls,
        "active_cars": active_cars,
        "waiting_users": waiting_users,
        "mock_eta_minutes": eta_minutes,
        "calls_detail": ranked_calls
    }
