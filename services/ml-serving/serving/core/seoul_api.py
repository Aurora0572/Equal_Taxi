# serving/core/seoul_api.py
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Final

import httpx
import pandas as pd
from fastapi import HTTPException

from ..constants import BASE_URL
from ..core.utils import get_env

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────
# 환경 변수
# ────────────────────────────────────────────────────────────────
API_KEY_USAGE: Final[str] = get_env("CALLTAXI_USAGE_KEY")
API_KEY_DEST:  Final[str] = get_env("CALLTAXI_DEST_KEY")

# ────────────────────────────────────────────────────────────────
# 공통 설정
# ────────────────────────────────────────────────────────────────
EXPECTED_USAGE_COLS: list[str] = [
    "기준일", "차량운행", "접수건", "탑승건",
    "평균대기시간", "평균요금", "평균승차거리",
]

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼 이름 공백 제거 및 순서·중복 정리"""
    df = df.rename(columns=lambda c: str(c).strip())

    # 예상 컬럼이 모두 존재하면 순서 맞춰 slice
    if set(EXPECTED_USAGE_COLS).issubset(df.columns):
        df = df[EXPECTED_USAGE_COLS]
    else:
        logger.warning("예상과 다른 컬럼 구조: %s", df.columns.tolist())
    return df


# ────────────────────────────────────────────────────────────────
# 내부: Excel 혹은 HTML → DataFrame
# ────────────────────────────────────────────────────────────────
async def _fetch_table(url: str) -> pd.DataFrame:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    content = resp.content
    if b"<table" in content[:100].lower():
        tables = pd.read_html(BytesIO(content), flavor="lxml", encoding="euc-kr")
        if not tables:
            raise HTTPException(500, "HTML 파싱 실패")
        return tables[0]

    # Excel: 헤더 1행이 있을 수도, 없을 수도 있어 skiprows=0 으로 읽고 후처리
    return pd.read_excel(BytesIO(content), engine="openpyxl", skiprows=0)


# ────────────────────────────────────────────────────────────────
# 1) 일자별 이용 통계
# ────────────────────────────────────────────────────────────────
async def fetch_daily_usage_data(date: str) -> pd.DataFrame:
    url = f"{BASE_URL}/newEXCEL0001.asp?key={API_KEY_USAGE}&sDate={date}&eDate={date}"
    df = await _fetch_table(url)

    # ── NEW: 컬럼이 0,1,2… 일 때 첫 행을 헤더로 승격 ───────────────
    if all(isinstance(c, (int, float)) for c in df.columns):
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

    df = _normalize_columns(df)

    # 누락 컬럼 보정
    if len(df.columns) < len(EXPECTED_USAGE_COLS):
        for col in EXPECTED_USAGE_COLS:
            if col not in df.columns:
                df[col] = pd.NA
        df = df[EXPECTED_USAGE_COLS]

    # 타입 캐스팅
    df["기준일"] = df["기준일"].astype(str, errors="ignore")
    num_cols = EXPECTED_USAGE_COLS[1:]
    df[num_cols] = df[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0)

    return df
