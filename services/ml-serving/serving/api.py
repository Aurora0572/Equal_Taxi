import os
import logging
from io import BytesIO
from typing import Dict

import google.generativeai as genai
import pandas as pd
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from fastapi_cache.backends.inmemory import InMemoryBackend

from .constants import REQUIRED_COLS, DEFAULT_DATE, BASE_URL
from .schemas import UsageResponse, DestinationResponse, UsageSummary

# -----------------------------------------
# 환경변수 & 로깅 설정
# -----------------------------------------
load_dotenv()
logger = logging.getLogger("taxi_api")
logging.basicConfig(level=logging.INFO)

API_KEY_USAGE = os.getenv("CALLTAXI_USAGE_KEY")
API_KEY_DEST = os.getenv("CALLTAXI_DEST_KEY")
TMAP_KEY = os.getenv("TMAP_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

if not API_KEY_USAGE or not API_KEY_DEST:
    logger.warning("API 키가 .env 파일에 설정되지 않았습니다!")

# -----------------------------------------
# FastAPI 앱
# -----------------------------------------
app = FastAPI(
    title="스마트 장애인 콜택시 시스템",
    description="서울시 장애인 콜택시 실시간 이용현황 + 예측/배차 API",
    version="2.2",
)

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend())

# -----------------------------------------
# 공통 함수
# -----------------------------------------
async def _fetch_excel_from_api(url: str) -> pd.DataFrame:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.RequestError as e:
        logger.error(f"API 요청 실패: {e}")
        raise HTTPException(status_code=502, detail="서울시 API 요청 실패")
    except httpx.HTTPStatusError as e:
        logger.error(f"API 상태코드 오류: {e.response.status_code}")
        raise HTTPException(status_code=502, detail=f"서울시 API 응답 오류: {e.response.status_code}")

    content = resp.content
    head = content[:100].lower()

    if b"<table" in head:
        try:
            tables = pd.read_html(BytesIO(content), flavor="lxml", encoding="euc-kr")
            if not tables:
                raise ValueError("HTML 응답에서 테이블을 찾지 못했습니다.")
            return tables[0]
        except Exception as e:
            logger.error(f"HTML 테이블 파싱 실패: {e}")
            with open("debug_response.html", "wb") as f:
                f.write(content)
            raise HTTPException(status_code=500, detail=f"HTML 파싱 실패: {e}")

    try:
        df = pd.read_excel(BytesIO(content), engine="openpyxl", skiprows=1)
        return df
    except Exception as e:
        logger.error(f"엑셀 파싱 실패: {e}")
        raise HTTPException(status_code=500, detail=f"엑셀 파싱 실패: {e}")

# -----------------------------------------
# 서울시 콜택시 API
# -----------------------------------------
async def fetch_daily_usage_data(date: str = "20250131") -> pd.DataFrame:
    start_date = date
    url = f"{BASE_URL}/newEXCEL0001.asp?key={API_KEY_USAGE}&sDate={date}&eDate={date}"
    df = await _fetch_excel_from_api(url)
    logger.info(f"Received columns: {df.columns.tolist()}")

    expected_cols = ["기준일", "차량운행", "접수건", "탑승건", "평균대기시간", "평균요금", "평균승차거리"]
    if len(df.columns) >= len(expected_cols):
        df = df.iloc[:, :len(expected_cols)]
        df.columns = expected_cols

    df["기준일"] = df["기준일"].astype(str)
    df = df[df["기준일"].str.match(r"^\d{4}-?\d{2}-?\d{2}$|^\d{8}$")]
    
    numeric_cols = ["차량운행", "접수건", "탑승건", "평균대기시간", "평균요금", "평균승차거리"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df

async def fetch_best_100_destinations(start_date: str = "20250101") -> pd.DataFrame:
    url = f"{BASE_URL}/newEXCEL0002.asp?key={API_KEY_DEST}&sDate={start_date}"
    df = await _fetch_excel_from_api(url)
    logger.info(f"Best Destinations columns: {df.columns.tolist()}")

    if len(df.columns) >= 5 and "cnt" not in df.columns:
        df = df.iloc[:, :5]
        df.columns = ["usedate", "oc", "og", "dong", "cnt"]

    df["장소명"] = df["oc"].astype(str) + " " + df["og"].astype(str) + " " + df["dong"].astype(str)
    df["이용건수"] = pd.to_numeric(df["cnt"], errors="coerce").fillna(0).astype(int)
    return df

# -----------------------------------------
# Tmap API (ETA)
# -----------------------------------------
async def get_tmap_travel_time(start_lng: float, start_lat: float, end_lng: float, end_lat: float) -> int:
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
        data = r.json()
        return data["features"][0]["properties"]["totalTime"]

# -----------------------------------------
# 엔드포인트
# -----------------------------------------
@app.get("/v2/usage", response_model=UsageResponse)
async def get_usage_stats(
    date: str = "20250131",
    start_lng: float = Query(126.9784),
    start_lat: float = Query(37.5667),
):
    """
    이용 통계 + 각 상위 목적지 ETA 포함
    """
    try:
        df = await fetch_daily_usage_data(date)

        top_locations_series = (
            df.groupby("기준일")["탑승건"]
            .sum()
            .nlargest(10)
            .rename_axis(None)
        )

        top_locations = {}
        for k, v in top_locations_series.items():
            eta_seconds = None
            eta_minutes = None
            try:
                # 실제 목적지 좌표 없으므로 임시 offset 사용
                eta_seconds = await get_tmap_travel_time(
                    start_lng, start_lat, start_lng + 0.01, start_lat + 0.01
                )
                eta_minutes = round(eta_seconds / 60, 1)
            except Exception as e:
                logger.warning(f"ETA 계산 실패: {e}")

            top_locations[str(k)] = {
                "rides": int(v),
                "estimated_seconds": eta_seconds,
                "estimated_minutes": eta_minutes,
            }

        summary = UsageSummary(
            date=date,
            total_requests=int(df["접수건"].sum()),
            total_rides=int(df["탑승건"].sum()),
            total_vehicles=int(df["차량운행"].sum()),
            avg_waiting_time=float(df["평균대기시간"].mean()),
            avg_fare=float(df["평균요금"].mean()),
            avg_distance=float(df["평균승차거리"].mean()),
            top_locations=top_locations,
        )
        return UsageResponse(summary=summary)
    except Exception as e:
        logger.exception("Usage stats error")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v2/best_destinations", response_model=DestinationResponse)
@cache(expire=300)
async def get_best_destinations(
    sDate: str = DEFAULT_DATE[:-2] + "01",
    start_lng: float = Query(126.9784),
    start_lat: float = Query(37.5667),
):
    """
    인기 목적지 + Tmap ETA 정보 반환
    """
    try:
        df = await fetch_best_100_destinations(sDate)
        top_places = df[["장소명", "이용건수"]].sort_values(by="이용건수", ascending=False).head(10)

        results = []
        for row in top_places.to_dict(orient="records"):
            try:
                eta_sec = await get_tmap_travel_time(
                    start_lng, start_lat,
                    start_lng + 0.01, start_lat + 0.01  # 실제 좌표로 변경 가능
                )
                row["estimated_seconds"] = eta_sec
                row["estimated_minutes"] = round(eta_sec / 60, 1)
            except Exception as e:
                logger.warning(f"ETA 계산 실패: {e}")
                row["estimated_seconds"] = None
                row["estimated_minutes"] = None
            results.append(row)

        return {
            "start_date": sDate,
            "top_destinations": results,
        }
    except Exception as e:
        logger.exception("베스트 목적지 API 처리 중 오류")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask_gemini")
async def ask_gemini(prompt: str):
    """
    Gemini 2.5 Pro 모델에게 질문하고 답변 받기
    """
    try:
        model = genai.GenerativeModel("gemini-2.5-pro")
        response = model.generate_content(prompt)
        return {"prompt": prompt, "response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")
