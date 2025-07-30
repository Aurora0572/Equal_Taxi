from __future__ import annotations
from typing import Dict, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# ===== 예측 입력 (ML 모델 입력 데이터) =====
class InputData(BaseModel):
    시간대: int = Field(..., ge=0, le=23, description="시간 (0~23시)")
    위치: str
    날씨: str
    휠체어YN: int = Field(..., ge=0, le=1, description="휠체어 탑승 여부 (0 또는 1)")
    해당지역운행차량수: int = Field(..., ge=0, description="해당 지역 운행 차량 수 (대)")
    해당지역이용자수: int = Field(..., ge=0, description="해당 지역 이용자 수 (명)")


# ===== 배차 요청 관련 데이터 모델 =====
class CallRequest(BaseModel):
    user_id: str
    pickup_location: str
    destination: str
    wheelchair: bool = False
    destination_type: str = "general"  # general / hospital 등
    medical_appointment: bool = False
    special_requirements: Optional[List[str]] = None


class DriverInfo(BaseModel):
    driver_id: str
    current_location: str
    wheelchair_capable: bool = False
    status: str = "available"  # available / busy 등


class DispatchRequest(BaseModel):
    request_id: str
    request_time: datetime
    call_request: CallRequest
    available_drivers: List[DriverInfo]
    weather: str = "맑음"


# ===== 통계/사용량 관련 모델 =====
class LocationStats(BaseModel):
    rides: int
    estimated_seconds: Optional[int] = None
    estimated_minutes: Optional[float] = None


class UsageSummary(BaseModel):
    date: str
    total_requests: int
    total_rides: int
    total_vehicles: int
    avg_waiting_time: float
    avg_fare: float
    avg_distance: float
    top_locations: Dict[str, LocationStats]


class UsageResponse(BaseModel):
    summary: UsageSummary


class Destination(BaseModel):
    장소명: str
    이용건수: int
    estimated_seconds: Optional[int] = None
    estimated_minutes: Optional[float] = None


class DestinationResponse(BaseModel):
    start_date: str
    top_destinations: List[Destination]


# ===== 실시간 mock 데이터 =====
class MockRealtimeResponse(BaseModel):
    calls: int = Field(
        ..., example=12, description="현재 콜 요청 수 (건)"
    )
    active_cars: int = Field(
        ..., example=5, description="현재 운행 중인 차량 수 (대)"
    )
    waiting_users: Optional[int] = Field(
        0, example=3, description="배차를 기다리는 사용자 수 (명, 없으면 0)"
    )
    priority_score: float = Field(
        ..., example=0.74, description="0.3~1.0 범위의 긴급도 점수 (비율)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "calls": 12,
                "active_cars": 5,
                "waiting_users": 3,
                "priority_score": 0.74
            }
        }


# ===== V2 Usage 응답 =====
class UsageV2Response(BaseModel):
    endpoint: str
    total_requests: int
    status: str
    estimated_minutes: Optional[float] = Field(
        None,
        example=12.3,
        description="평균 배차 예상 시간 (분, Tmap 기반)"
    )
    gemini_eta: Optional[float] = Field(
        None,
        example=15.5,
        description="Gemini AI가 통계를 기반으로 예측한 배차 예상 시간 (분)"
    )
    gemini_comment: Optional[str] = Field(
        None,
        example="교통 혼잡으로 배차 긴급도가 높습니다.",
        description="Gemini AI가 생성한 한 줄 요약"
    )
    mock_realtime: MockRealtimeResponse