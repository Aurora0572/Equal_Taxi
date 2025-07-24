from fastapi import FastAPI, HTTPException
import requests
import pandas as pd
from io import BytesIO

# ✅ FastAPI 앱 인스턴스
app = FastAPI(
    title="스마트 장애인 콜택시 시스템",
    description="서울시 장애인 콜택시 실시간 이용현황 + 예측/배차 API",
    version="2.0",
)

# ✅ 루트 엔드포인트
@app.get("/")
def root():
    return {
        "message": "🚕 스마트 장애인 콜택시 API 서버 작동 중입니다.",
        "endpoints": [
            "/usage?date=YYYYMMDD",
            "/best_destinations?sDate=YYYYMMDD"
        ]
    }

# ✅ 일별 이용현황 API
@app.get("/usage")
def get_daily_usage(date: str = "20250131"):
    try:
        df = fetch_daily_usage_data(date)

        summary = {
            "date": date,
            "total_requests": int(df["접수건"].sum()),
            "total_rides": int(df["탑승건"].sum()),
            "total_vehicles": int(df["차량운행"].sum()),
            "avg_waiting_time": round(df["평균대기시간"].mean(), 2),
            "avg_fare": round(df["평균요금"].mean(), 2),
            "avg_distance": round(df["평균승차거리"].mean(), 2)
        }

        top_locations = (
            df.groupby("출발지")[["탑승건"]]
            .sum()
            .sort_values(by="탑승건", ascending=False)
            .head(5)
            .reset_index()
            .rename(columns={"출발지": "location", "탑승건": "ride_count"})
            .to_dict(orient="records")
        )

        return {
            "summary": summary,
            "top_locations": top_locations
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ 베스트 목적지 API
@app.get("/best_destinations")
def get_best_destinations(sDate: str = "20250101"):
    try:
        df = fetch_best_100_destinations(sDate)
        top_places = df[["장소명", "이용건수"]].sort_values(by="이용건수", ascending=False).head(10)
        return {
            "start_date": sDate,
            "top_destinations": top_places.to_dict(orient="records")
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ 일별 이용현황 엑셀 파서
def fetch_daily_usage_data(date: str = "20250131") -> pd.DataFrame:
    url = f"http://m.calltaxi.sisul.or.kr/api/open/newEXCEL0001.asp?key=d197a032e00d4dfd139e4f6e2c7dc2df&eDate={date}"
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="일별 이용현황 데이터를 가져오는 데 실패했습니다.")

    try:
        df = pd.read_excel(BytesIO(response.content))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"엑셀 파싱 실패: {str(e)}")

    required_cols = ["출발지", "차량운행", "접수건", "탑승건", "평균대기시간", "평균요금", "평균승차거리"]
    for col in required_cols:
        if col not in df.columns:
            raise HTTPException(status_code=500, detail=f"필수 컬럼 누락: {col}")

    return df


# ✅ 베스트 목적지 엑셀 파서
def fetch_best_100_destinations(start_date: str = "20250101") -> pd.DataFrame:
    url = f"http://m.calltaxi.sisul.or.kr/api/open/newEXCEL0002.asp?key=fd055bf8b90d1b192bd870f910f0fddf&sDate={start_date}"
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="베스트 목적지 데이터를 가져오는 데 실패했습니다.")

    try:
        df = pd.read_excel(BytesIO(response.content))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"엑셀 파싱 실패: {str(e)}")

    if "장소명" not in df.columns or "이용건수" not in df.columns:
        raise HTTPException(status_code=500, detail="컬럼 누락: 장소명 또는 이용건수")

    return df
