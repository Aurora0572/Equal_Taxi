from pydantic import BaseModel
from typing import List

class Location(BaseModel):
    location: str
    ride_count: int

class UsageSummary(BaseModel):
    date: str
    total_requests: int
    total_rides: int
    total_vehicles: int
    avg_waiting_time: float
    avg_fare: float
    avg_distance: float

class UsageResponse(BaseModel):
    summary: UsageSummary
    top_locations: List[Location]

class Destination(BaseModel):
    장소명: str
    이용건수: int

class DestinationResponse(BaseModel):
    start_date: str
    top_destinations: List[Destination]