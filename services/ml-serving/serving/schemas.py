from __future__ import annotations  # 향후 버전과의 호환성을 위해 도입 (예: forward reference)

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field  # 데이터 검증 및 직렬화를 위한 pydantic 사용


# ----- 예측 입력 -----
class InputData(BaseModel):
    """
    수요 예측 또는 모델 입력에 사용되는 데이터 구조
    """
    시간대: int = Field(..., ge=0, le=23, description="시간(0~23시)")  # 0~23시 사이의 정수로 제한
    위치: str  # 지역 또는 장소 이름
    날씨: str  # 예: 맑음, 비, 흐림 등
    휠체어YN: int = Field(..., ge=0, le=1)  # 휠체어 가능 여부 (0: 아니오, 1: 예)
    해당지역운행차량수: int = Field(..., ge=0)  # 현재 지역에 운행 중인 차량 수
    해당지역이용자수: int = Field(..., ge=0)  # 현재 지역의 서비스 이용자 수


# ----- 배차용 -----
class CallRequest(BaseModel):
    """
    사용자의 호출 요청 정보
    """
    user_id: str  # 사용자 ID
    pickup_location: str  # 승차 위치
    destination: str  # 목적지
    wheelchair: bool = False  # 휠체어 지원 여부
    destination_type: str = "general"  # 목적지 유형 (병원, 약국 등)
    medical_appointment: bool = False  # 병원 예약 여부
    special_requirements: Optional[List[str]] = None  # 추가 요구사항 (예: 도우미 필요 등)


class DriverInfo(BaseModel):
    """
    운전자 정보
    """
    driver_id: str  # 운전자 ID
    current_location: str  # 현재 위치
    wheelchair_capable: bool = False  # 휠체어 지원 가능 차량 여부
    status: str = "available"  # 운전자 상태 (예: 'available', 'on_trip')


class DispatchRequest(BaseModel):
    """
    배차 요청 정보 (콜 요청 + 운전자 리스트)
    """
    request_id: str  # 요청 ID
    request_time: datetime  # 요청 시간
    call_request: CallRequest  # 호출 요청 정보
    available_drivers: List[DriverInfo]  # 현재 배차 가능한 운전자 목록
    weather: str = "맑음"  # 현재 날씨 정보