import httpx
from ..utils import get_env

TMAP_KEY = get_env("TMAP_API_KEY")

async def get_tmap_travel_time(start_lng, start_lat, end_lng, end_lat) -> int:
    url = "https://apis.openapi.sk.com/tmap/routes"
    headers = {"appKey": TMAP_KEY, "Content-Type": "application/json"}
    body = {
        "startX": str(start_lng),
        "startY": str(start_lat),
        "endX": str(end_lng),
        "endY": str(end_lat),
        "reqCoordType": "WGS84GEO",
        "resCoordType": "WGS84GEO",
        "searchOption": "0",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        return r.json()["features"][0]["properties"]["totalTime"]
