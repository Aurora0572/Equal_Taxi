from io import BytesIO
import pandas as pd
import httpx
from fastapi import HTTPException
from ..constants import BASE_URL
from ..utils import get_env
import logging

logger = logging.getLogger(__name__)

API_KEY_USAGE = get_env("CALLTAXI_USAGE_KEY")
API_KEY_DEST = get_env("CALLTAXI_DEST_KEY")

async def _fetch_excel_from_api(url: str) -> pd.DataFrame:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    content = resp.content
    head = content[:100].lower()

    if b"<table" in head:
        tables = pd.read_html(BytesIO(content), flavor="lxml", encoding="euc-kr")
        if not tables:
            raise HTTPException(status_code=500, detail="HTML 파싱 실패")
        return tables[0]

    return pd.read_excel(BytesIO(content), engine="openpyxl", skiprows=1)

async def fetch_daily_usage_data(date: str) -> pd.DataFrame:
    url = f"{BASE_URL}/newEXCEL0001.asp?key={API_KEY_USAGE}&sDate={date}&eDate={date}"
    df = await _fetch_excel_from_api(url)
    expected_cols = ["기준일", "차량운행", "접수건", "탑승건", "평균대기시간", "평균요금", "평균승차거리"]

    if len(df.columns) >= len(expected_cols):
        df = df.iloc[:, :len(expected_cols)]
        df.columns = expected_cols

    df["기준일"] = df["기준일"].astype(str)
    for col in expected_cols[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

async def fetch_best_100_destinations(start_date: str) -> pd.DataFrame:
    url = f"{BASE_URL}/newEXCEL0002.asp?key={API_KEY_DEST}&sDate={start_date}"
    df = await _fetch_excel_from_api(url)

    if len(df.columns) >= 5 and "cnt" not in df.columns:
        df = df.iloc[:, :5]
        df.columns = ["usedate", "oc", "og", "dong", "cnt"]

    df["장소명"] = df["oc"].astype(str) + " " + df["og"].astype(str) + " " + df["dong"].astype(str)
    df["이용건수"] = pd.to_numeric(df["cnt"], errors="coerce").fillna(0).astype(int)
    return df
