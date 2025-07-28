# services/data_pipeline/best_destinations_loader.py

import pandas as pd

def load_best_destinations(s_date: str) -> pd.DataFrame:
    """
    서울시설공단 API에서 '목적지 베스트 100' 데이터를 로드합니다.
    :param s_date: 시작일 (YYYYMMDD)
    :return: pandas DataFrame
    """
    base_url = "http://m.calltaxi.sisul.or.kr/api/open/newEXCEL0002.asp"
    key = "d197a032e00d4dfd139e4f6e2c7dc2df"  # ← 본인의 실제 인증 키로 대체
    url = f"{base_url}?key={key}&sDate={s_date}"

    try:
        df = pd.read_excel(url, engine='openpyxl')  # ✅ 필수: engine 명시
        return df
    except Exception as e:
        raise RuntimeError(f"엑셀 파싱 실패: {e}")
