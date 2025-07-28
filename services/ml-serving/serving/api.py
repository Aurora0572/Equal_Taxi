import os
import logging
from io import BytesIO
from typing import Dict

import pandas as pd
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from fastapi_cache.backends.inmemory import InMemoryBackend

from .constants import REQUIRED_COLS, DEFAULT_DATE, BASE_URL
from .schemas import UsageResponse, DestinationResponse, UsageSummary  # UsageSummary 추가

# -----------------------------------------
# 환경변수 & 로깅 설정
# -----------------------------------------
load_dotenv()
logger = logging.getLogger("taxi_api")
logging.basicConfig(level=logging.INFO)

API_KEY_USAGE = os.getenv("CALLTAXI_USAGE_KEY")
API_KEY_DEST = os.getenv("CALLTAXI_DEST_KEY")

if not API_KEY_USAGE or not API_KEY_DEST:
    logger.warning("API 키가 .env 파일에 설정되지 않았습니다!")

# -----------------------------------------
# FastAPI 앱
# -----------------------------------------
app = FastAPI(
    title="스마트 장애인 콜택시 시스템",
    description="서울시 장애인 콜택시 실시간 이용현황 + 예측/배차 API",
    version="2.0",
)

# CORS 미들웨어 추가
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
# 루트 엔드포인트
# -----------------------------------------
@app.get("/")
async def root() -> Dict:
    return {
        "message": "🚕 스마트 장애인 콜택시 API 서버 작동 중입니다.",
        "endpoints": [
            "/usage?date=YYYYMMDD",
            "/best_destinations?sDate=YYYYMMDD"
        ]
    }

# -----------------------------------------
# 비동기 HTTP 요청 공통 함수
# -----------------------------------------
async def _fetch_excel_from_api(url: str) -> pd.DataFrame:
    """서울시 콜택시 API에서 데이터를 비동기로 가져옴"""
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

    # HTML 테이블 응답 처리
    if b"<table" in head:
        try:
            # euc-kr 인코딩으로 변경
            tables = pd.read_html(BytesIO(content), flavor="lxml", encoding="euc-kr")
            if not tables:
                raise ValueError("HTML 응답에서 테이블을 찾지 못했습니다.")
            return tables[0]
        except Exception as e:
            logger.error(f"HTML 테이블 파싱 실패: {e}")
            with open("debug_response.html", "wb") as f:
                f.write(content)
            raise HTTPException(status_code=500, detail=f"HTML 파싱 실패: {e}")

    # Excel 파일 응답 처리 (openpyxl 엔진 + skiprows 1)
    try:
        df = pd.read_excel(BytesIO(content), engine="openpyxl", skiprows=1)
        return df
    except Exception as e:
        logger.error(f"엑셀 파싱 실패: {e}")
        raise HTTPException(status_code=500, detail=f"엑셀 파싱 실패: {e}")

# -----------------------------------------
# 데이터 로드 함수
# -----------------------------------------
async def fetch_daily_usage_data(date: str = "20250131") -> pd.DataFrame:
    start_date = date
    url = f"{BASE_URL}/newEXCEL0001.asp?key={API_KEY_USAGE}&sDate={start_date}&eDate={date}"
    df = await _fetch_excel_from_api(url)

    logger.info(f"Received columns: {df.columns.tolist()}")

    # 강제로 컬럼 이름 지정 (엑셀 구조가 항상 같다면)
    expected_cols = ["기준일", "차량운행", "접수건", "탑승건", "평균대기시간", "평균요금", "평균승차거리"]
    if len(df.columns) >= len(expected_cols):
        df = df.iloc[:, :len(expected_cols)]
        df.columns = expected_cols
    
    # 숫자 컬럼 강제 변환
    numeric_cols = ["차량운행", "접수건", "탑승건", "평균대기시간", "평균요금", "평균승차거리"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Verify required columns
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        logger.error(f"필수 컬럼 누락: {', '.join(missing_cols)}")
        df.to_csv("debug_columns.csv", encoding='utf-8-sig')
        raise HTTPException(
            status_code=500,
            detail=f"필수 컬럼 누락: {', '.join(missing_cols)}. 받은 컬럼: {', '.join(df.columns)}"
        )

    return df

async def fetch_best_100_destinations(start_date: str = "20250101") -> pd.DataFrame:
    url = f"{BASE_URL}/newEXCEL0002.asp?key={API_KEY_DEST}&sDate={start_date}"
    df = await _fetch_excel_from_api(url)

    logger.info(f"Best Destinations columns: {df.columns.tolist()}")

    # 컬럼 이름이 숫자로만 들어오면 수동으로 지정
    if len(df.columns) >= 5 and "cnt" not in df.columns:
        df = df.iloc[:, :5]
        df.columns = ["usedate", "oc", "og", "dong", "cnt"]

    required_cols = {"oc", "og", "dong", "cnt"}
    if not required_cols.issubset(set(df.columns)):
        raise HTTPException(status_code=500, detail="필수 컬럼 누락: oc, og, dong, cnt")

    # 장소명 컬럼 생성
    df["장소명"] = df["oc"].astype(str) + " " + df["og"].astype(str) + " " + df["dong"].astype(str)
    df["이용건수"] = pd.to_numeric(df["cnt"], errors="coerce").fillna(0).astype(int)

    return df

# -----------------------------------------
# 엔드포인트
# -----------------------------------------
@app.get("/v2/usage", response_model=UsageResponse)
async def get_usage_stats(date: str = "20250131"):
    try:
        df = await fetch_daily_usage_data(date)

        # 일자별 탑승건 상위 10개
        top_locations = (
            df.groupby("기준일")["탑승건"]
            .sum()
            .nlargest(10)
            .to_dict()
        )

        summary = UsageSummary(
            date=date,
            total_requests=int(df["접수건"].sum()),
            total_rides=int(df["탑승건"].sum()),
            total_vehicles=int(df["차량운행"].sum()),
            avg_waiting_time=float(df["평균대기시간"].mean()),
            avg_fare=float(df["평균요금"].mean()),
            avg_distance=float(df["평균승차거리"].mean()),
            top_locations={str(k): int(v) for k, v in top_locations.items()}
        )

        return UsageResponse(summary=summary)

    except Exception as e:
        logger.exception("Usage stats error")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v2/best_destinations", response_model=DestinationResponse)
@cache(expire=300)
async def get_best_destinations(sDate: str = DEFAULT_DATE[:-2] + "01"):
    try:
        df = await fetch_best_100_destinations(sDate)
        top_places = df[["장소명", "이용건수"]].sort_values(by="이용건수", ascending=False).head(10)
        return {
            "start_date": sDate,
            "top_destinations": top_places.to_dict(orient="records")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("베스트 목적지 API 처리 중 오류")
        raise HTTPException(status_code=500, detail=str(e))