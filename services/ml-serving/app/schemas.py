from __future__ import annotations

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ----- 예측 입력 -----
class InputData(BaseModel):
    시간대: int = Field(..., ge=0, le=23, description="시간(0~23시)")
    위치: str
    날씨: str
    휠체어YN: int = Field(..., ge=0, le=1)
    해당지역운행차량수: int = Field(..., ge=0)
    해당지역이용자수: int = Field(..., ge=0)


# ----- 배차용 -----
class CallRequest(BaseModel):
    user_id: str
    pickup_location: str
    destination: str
    wheelchair: bool = False
    destination_type: str = "general"  # hospital, pharmacy, government, education, general
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
