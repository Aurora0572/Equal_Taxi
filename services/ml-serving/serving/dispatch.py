from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import asyncio

from .schemas import DispatchRequest, CallRequest, DriverInfo
from .utils import (
    load_model_assets,
    predict_waiting_time_from_request,
    estimate_usage_stats,
)
from .api import fetch_daily_usage_data  # 오픈 API 함수 임포트
from .routers.mock import realtime_mock  # priority_score 연동 추가


# ---------------------------------------------------------------------------
# 기초 데이터 (지역 및 날씨 영향도)
# ---------------------------------------------------------------------------

LOCATION_DATA = {
    "강남": {"code": 0, "lat": 37.5172, "lon": 127.0473, "density": "high"},
    "종로": {"code": 1, "lat": 37.5735, "lon": 126.9794, "density": "high"},
    "노원": {"code": 2, "lat": 37.6542, "lon": 127.0568, "density": "medium"},
    "송파": {"code": 3, "lat": 37.5145, "lon": 127.1054, "density": "high"},
    "영등포": {"code": 4, "lat": 37.5264, "lon": 126.8963, "density": "medium"},
    "성동": {"code": 5, "lat": 37.5633, "lon": 127.0367, "density": "medium"},
    "강서": {"code": 6, "lat": 37.5509, "lon": 126.8495, "density": "low"},
    "마포": {"code": 7, "lat": 37.5663, "lon": 126.9018, "density": "high"},
    "서초": {"code": 8, "lat": 37.4837, "lon": 127.0324, "density": "high"},
    "중구": {"code": 9, "lat": 37.5641, "lon": 126.9979, "density": "high"},
}

WEATHER_IMPACT = {
    "맑음": {"difficulty": 1.0, "demand_multiplier": 1.0},
    "흐림": {"difficulty": 1.1, "demand_multiplier": 1.1},
    "비": {"difficulty": 1.3, "demand_multiplier": 1.4},
    "눈": {"difficulty": 1.5, "demand_multiplier": 1.6},
}


# ---------------------------------------------------------------------------
# 사용자/운전자 프로필 구조 정의 (임시)
# ---------------------------------------------------------------------------

@dataclass
class UserProfile:
    user_id: str
    total_rides: int = 0
    avg_waiting_time: float = 0.0
    wheelchair_user: bool = False
    frequent_locations: List[str] = None
    reliability_score: float = 1.0
    special_needs: List[str] = None


@dataclass
class DriverProfile:
    driver_id: str
    wheelchair_capable: bool
    service_score: float = 1.0
    avg_pickup_time: float = 15.0
    completed_rides: int = 0
    specialty_areas: List[str] = None


# ---------------------------------------------------------------------------
# 스마트 배차 알고리즘
# ---------------------------------------------------------------------------

class SmartDispatchAlgorithm:
    def __init__(self):
        self.active_requests: Dict[str, Dict] = {}
        self.driver_pool: Dict[str, Dict] = {}
        self.historical_patterns: Dict = {}
        self.real_time_traffic: Dict = {}

        self.wait_model, self.le_loc, self.le_weather = load_model_assets()

    async def dynamic_dispatch(self, request: Dict, available_drivers: List[Dict]) -> Dict:
        """
        요청 정보를 기반으로 우선순위 점수(priority_score)를 포함한 스마트 배차 수행
        """
        # ① mock 데이터를 통해 calls_detail 가져오기 (priority_score 사용)
        priority_boost = 0.0
        try:
            mock_data = await realtime_mock()
            calls_detail = mock_data.get("calls_detail", [])
            for call in calls_detail:
                # ID 또는 user_id를 기준으로 매칭
                if str(call.get("id")) == str(request.get("request_id")) or \
                   str(call.get("id")) == str(request.get("user_id")):
                    priority_boost = call.get("priority_score", 0.0)
                    break
        except Exception as e:
            print(f"priority_score 불러오기 실패: {e}")

        # ② 실시간 수요/공급 데이터 보정
        try:
            vehicles, users = estimate_usage_stats(request.get("pickup_location"))
            request["num_vehicles"] = vehicles
            request["num_users"] = users
        except:
            request["num_vehicles"] = 10
            request["num_users"] = 20

        # ③ 긴급도 평가
        urgency = self.calculate_urgency_score(request)

        # ④ priority_score 가중치 반영 (2배 효과)
        urgency *= (1 + 2 * priority_boost)

        # ⑤ 긴급 배차 기준 확인
        system_load = len(self.active_requests) / max(len(available_drivers), 1)
        urgency_threshold = 50 if system_load > 3 else 30
        if urgency > urgency_threshold:
            return self.emergency_dispatch(request, available_drivers)

        # ⑥ 스코어 기반 일반 배차
        dispatch_scores = []
        for driver in available_drivers:
            if request.get('wheelchair') and not driver.get('wheelchair_capable'):
                continue

            efficiency = self.calculate_efficiency_score(driver, request)
            fairness = self.calculate_fairness_score(driver, request)
            total_score = urgency * 0.4 + efficiency * 0.4 + fairness * 0.2

            dispatch_scores.append({
                'driver': driver,
                'score': total_score,
                'components': {
                    'urgency': urgency,
                    'efficiency': efficiency,
                    'fairness': fairness
                }
            })

        if not dispatch_scores:
            raise HTTPException(status_code=404, detail="배차 가능한 차량이 없습니다")

        best_match = max(dispatch_scores, key=lambda x: x['score'])
        self.learn_from_dispatch(request, best_match)
        return self.create_dispatch_result(request, best_match)

    def calculate_urgency_score(self, request: Dict) -> float:
        urgency = 0.0
        now = datetime.now(timezone.utc)
        wait_minutes = (now - request['request_time']).total_seconds() / 60
        urgency += math.exp(wait_minutes / 15) * 10

        if request.get('wheelchair'):
            urgency += 30
            if request.get('medical_appointment'):
                urgency += 50

        urgency *= {
            'hospital': 2.0, 'pharmacy': 1.8, 'government': 1.5,
            'education': 1.3, 'general': 1.0
        }.get(request.get('destination_type', 'general'), 1.0)

        if request.get('weather') in ['비', '눈'] and request.get('wheelchair'):
            urgency *= 1.5

        if request.get('destination_type') == 'hospital' and now.hour >= 16:
            urgency *= 1.5

        user_profile = self.get_user_profile(request.get('user_id'))
        if user_profile and user_profile.reliability_score < 0.8:
            urgency *= 0.8

        if self.predict_waiting_time(request) >= 25:
            urgency *= 1.1

        return urgency

    def calculate_efficiency_score(self, driver: Dict, request: Dict) -> float:
        efficiency = 100.0
        travel_time = self.estimate_real_travel_time(
            driver['current_location'],
            request['pickup_location'],
            request.get('weather', '맑음')
        )
        efficiency -= travel_time * 2

        if self.find_nearby_future_requests(request['destination'], travel_time + 20):
            efficiency += 10

        match_score = self.calculate_driver_user_match(driver, request)
        efficiency += match_score * 20

        density_bonus = {'high': 15, 'medium': 5, 'low': 0}
        dest_density = LOCATION_DATA[request['destination']]['density']
        efficiency += density_bonus.get(dest_density, 0)

        fatigue = self.calculate_driver_fatigue(driver['driver_id'])
        if fatigue > 0.7:
            efficiency *= 0.7

        return efficiency

    def calculate_fairness_score(self, driver: Dict, request: Dict) -> float:
        fairness = 50.0
        user_profile = self.get_user_profile(request.get('user_id'))
        if user_profile and user_profile.avg_waiting_time > 25:
            fairness += 20

        if self.get_location_service_stats(request['pickup_location']) < 0.8:
            fairness += 15

        if self.get_driver_daily_rides(driver['driver_id']) < self.get_average_daily_rides() * 0.8:
            fairness += 10

        if self.predict_waiting_time(request) >= 25:
            fairness += 10

        return fairness

    def emergency_dispatch(self, request: Dict, drivers: List[Dict]) -> Dict:
        suitable = [d for d in drivers if not request.get('wheelchair') or d.get('wheelchair_capable')]
        if not suitable:
            raise HTTPException(status_code=404, detail="긴급 배차 가능 차량 없음")

        for driver in suitable:
            driver['eta'] = self.estimate_real_travel_time(
                driver['current_location'], request['pickup_location'], request.get('weather', '맑음')
            )

        fastest_driver = min(suitable, key=lambda x: x['eta'])
        return {
            'driver': fastest_driver,
            'score': 999,
            'components': {'urgency': 999, 'efficiency': 0, 'fairness': 0}
        }

    def estimate_real_travel_time(self, from_loc: str, to_loc: str, weather: str) -> float:
        from_data, to_data = LOCATION_DATA[from_loc], LOCATION_DATA[to_loc]
        R = 6371
        dlat = math.radians(to_data['lat'] - from_data['lat'])
        dlon = math.radians(to_data['lon'] - from_data['lon'])
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(from_data['lat'])) * math.cos(math.radians(to_data['lat'])) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        base_speed = 25
        hour = datetime.now().hour
        if hour in [8, 9, 18, 19]:
            base_speed *= 0.6
        elif hour in [12, 13]:
            base_speed *= 0.8
        elif hour < 6:
            base_speed *= 1.3

        base_speed /= WEATHER_IMPACT.get(weather, {}).get('difficulty', 1.0)
        travel_time = (distance / base_speed) * 60
        travel_time *= self.real_time_traffic.get((from_loc, to_loc), 1.0)
        return travel_time

    def calculate_driver_user_match(self, driver: Dict, request: Dict) -> float:
        score = 0.0
        profile = self.get_driver_profile(driver['driver_id'])

        if request.get('wheelchair') and driver.get('wheelchair_capable'):
            if profile and profile.specialty_areas and 'wheelchair_expert' in profile.specialty_areas:
                score += 2.0

        if request['pickup_location'] in driver.get('specialty_areas', []):
            score += 1.5
        if profile:
            score += profile.service_score

        return score

    def find_nearby_future_requests(self, location: str, eta: float) -> List[Dict]:
        return [
            r for r in self.active_requests.values()
            if r['pickup_location'] == location and
            (datetime.now() - r['request_time']).total_seconds() / 60 < eta + 30
        ]

    def learn_from_dispatch(self, request: Dict, dispatch_result: Dict):
        print(f"📦 기록: {request['request_id']} → {dispatch_result['driver']['driver_id']}")

    def calculate_driver_fatigue(self, driver_id: str) -> float:
        return 0.3  # 예시: 평소보다 덜 피로한 상태

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        return UserProfile(user_id=user_id, reliability_score=1.0)

    def get_driver_profile(self, driver_id: str) -> Optional[DriverProfile]:
        return DriverProfile(driver_id=driver_id, wheelchair_capable=True, service_score=1.2)

    def get_location_service_stats(self, location: str) -> float:
        return 0.85

    def get_driver_daily_rides(self, driver_id: str) -> int:
        return 10

    def get_average_daily_rides(self) -> float:
        return 12.0

    def predict_waiting_time(self, request: Dict) -> float:
        return predict_waiting_time_from_request(
            self.wait_model, self.le_loc, self.le_weather,
            {
                "pickup_location": request.get("pickup_location"),
                "weather": request.get("weather", "맑음"),
                "wheelchair": request.get("wheelchair", False),
                "num_vehicles": request.get("num_vehicles", 10),
                "num_users": request.get("num_users", 20),
            },
            default_hour=datetime.now().hour,
        )

    def create_dispatch_result(self, request: Dict, match: Dict) -> Dict:
        driver = match['driver']
        eta = self.estimate_real_travel_time(
            driver['current_location'], request['pickup_location'], request.get('weather', '맑음')
        )
        return {
            "driver_id": driver['driver_id'],
            "estimated_pickup_time": round(eta, 1),
            "dispatch_score": round(match['score'], 2),
            "dispatch_reason": self.generate_dispatch_reason(match['components']),
            "user_message": self.generate_user_message(eta, request)
        }

    def generate_dispatch_reason(self, components: Dict) -> str:
        reasons = []
        if components['urgency'] > 70: reasons.append("긴급 우선 배차")
        if components['efficiency'] > 80: reasons.append("최적 경로")
        if components['fairness'] > 60: reasons.append("서비스 균형")
        return ", ".join(reasons) if reasons else "종합 최적화"

    def generate_user_message(self, eta: float, request: Dict) -> str:
        if request.get('wheelchair'):
            return f"휠체어 전용 차량이 약 {int(eta)}분 내 도착 예정입니다."
        return f"차량이 약 {int(eta)}분 내 도착 예정입니다."

    def global_optimization(self, all_requests: List[Dict], all_drivers: List[str]):
        return [{"request_id": r["request_id"], "driver_id": all_drivers[i % len(all_drivers)]} for i, r in enumerate(all_requests)]


# ---------------------------------------------------------------------------
# FastAPI Router 정의 및 엔드포인트 연결
# ---------------------------------------------------------------------------

router = APIRouter()
dispatch_algorithm = SmartDispatchAlgorithm()


@router.post("/smart_dispatch/")
async def smart_dispatch(dispatch_request: DispatchRequest):
    request_info = {
        'request_id': dispatch_request.request_id,
        'request_time': dispatch_request.request_time,
        'user_id': dispatch_request.call_request.user_id,
        'pickup_location': dispatch_request.call_request.pickup_location,
        'destination': dispatch_request.call_request.destination,
        'wheelchair': dispatch_request.call_request.wheelchair,
        'destination_type': dispatch_request.call_request.destination_type,
        'medical_appointment': dispatch_request.call_request.medical_appointment,
        'weather': dispatch_request.weather
    }

    drivers = [
        {
            'driver_id': d.driver_id,
            'current_location': d.current_location,
            'wheelchair_capable': d.wheelchair_capable,
            'specialty_areas': d.specialty_areas
        }
        for d in dispatch_request.available_drivers
        if d.status == "available"
    ]

    try:
        return await dispatch_algorithm.dynamic_dispatch(request_info, drivers)
    except HTTPException:
        raise
    except Exception as e:
        print("❌ 예외:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch_optimize/")
async def batch_optimize(requests: List[DispatchRequest]):
    all_requests = []
    all_drivers = set()

    for req in requests:
        all_requests.append({
            'request_id': req.request_id,
            'request_time': req.request_time,
            'user_id': req.call_request.user_id,
            'pickup_location': req.call_request.pickup_location,
            'destination': req.call_request.destination,
            'wheelchair': req.call_request.wheelchair,
            'destination_type': req.call_request.destination_type,
            'weather': req.weather
        })
        for driver in req.available_drivers:
            all_drivers.add(driver.driver_id)

    return {"assignments": dispatch_algorithm.global_optimization(all_requests, list(all_drivers))}


@router.get("/system_status/")
async def get_system_status():
    active_count = len(dispatch_algorithm.active_requests)
    return {
        "total_active_requests": active_count,
        "location_statistics": {
            loc: {
                "active_requests": sum(
                    1 for r in dispatch_algorithm.active_requests.values()
                    if r.get('pickup_location') == loc
                ),
                "service_rate": dispatch_algorithm.get_location_service_stats(loc)
            }
            for loc in LOCATION_DATA
        },
        "system_load": "high" if active_count > 100 else "normal",
        "timestamp": datetime.now()
    }


@router.post("/update_profile/")
async def update_user_profile(user_id: str, profile_data: Dict):
    return {"status": "updated", "user_id": user_id}


@router.get("/real_time_demand/")
async def get_real_time_demand(location: str, date: str = "20250131"):
    try:
        df = fetch_daily_usage_data(date)
        filtered = df[df["출발지"].str.contains(location)]
        total_rides = int(filtered["운행건수"].sum())
        return {"location": location, "date": date, "rides": total_rides}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
