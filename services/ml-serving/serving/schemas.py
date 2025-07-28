from __future__ import annotations
from typing import Dict, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# ===== 예측 입력 =====
class InputData(BaseModel):
    시간대: int = Field(..., ge=0, le=23, description="시간(0~23시)")
    위치: str
    날씨: str
    휠체어YN: int = Field(..., ge=0, le=1)
    해당지역운행차량수: int = Field(..., ge=0)
    해당지역이용자수: int = Field(..., ge=0)


# ===== 배차 요청 =====
class CallRequest(BaseModel):
    user_id: str
    pickup_location: str
    destination: str
    wheelchair: bool = False
    destination_type: str = "general"
    medical_appointment: bool = False
    special_requirements: Optional[List[str]] = None


class DriverInfo(BaseModel):
    driver_id: str
    current_location: str
    wheelchair_capable: bool = False
    status: str = "available"


class DispatchRequest(BaseModel):
    request_id: str
    request_time: datetime
    call_request: CallRequest
    available_drivers: List[DriverInfo]
    weather: str = "맑음"


# ===== API 응답 =====
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
