# 기본 라이브러리 및 머신러닝 관련 모듈 임포트
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# 머신러닝 학습/검증/인코딩 관련 모듈
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor

# 모델 저장용
import joblib
from pathlib import Path

# ✅ 모델 및 인코더 저장 폴더 생성 (없으면 생성)
Path("app/model").mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# ✅ 더미 데이터 생성 함수
# ---------------------------------------------------------------------------
def generate_data(n_rows=5000):
    """
    대기시간 예측을 위한 학습용 더미 데이터 생성
    - 시간, 위치, 날씨, 휠체어 여부 등 다양한 입력 변수를 포함
    """
    start_time = datetime(2024, 7, 1, 6)  # 시작 시간 설정
    locations = ['강남', '종로', '노원', '송파', '영등포', '성동']  # 지역 후보
    weather_types = ['맑음', '흐림', '비', '눈']  # 날씨 종류

    data = []
    for i in range(n_rows):
        timestamp = start_time + timedelta(minutes=15 * i)  # 15분 간격 샘플 생성
        location = random.choice(locations)
        weather = random.choice(weather_types)
        wheelchair = random.choice(['Y', 'N'])  # 휠체어 여부 (Y/N)
        waiting_time = max(0, int(np.random.normal(10 if weather == '맑음' else 20, 5)))  # 날씨 기반 대기시간
        driver_count = random.randint(1, 10)
        user_count = random.randint(1, 15)

        data.append([
            timestamp.strftime('%Y-%m-%d %H:%M'),
            location,
            weather,
            wheelchair,
            waiting_time,
            driver_count,
            user_count
        ])

    return pd.DataFrame(data, columns=[
        '탑승시각', '위치', '날씨', '휠체어탑승여부', '대기시간(분)',
        '해당지역운행차량수', '해당지역이용자수'
    ])


# ---------------------------------------------------------------------------
# ✅ 모델 학습 및 저장 함수
# ---------------------------------------------------------------------------
def train_model():
    """
    더미 데이터를 이용해 XGBoost 모델 학습 후 모델 및 인코더 저장
    """
    df = generate_data()  # 더미 데이터 생성

    # 파생 변수 생성
    df['시간대'] = pd.to_datetime(df['탑승시각']).dt.hour  # 시간대 추출 (0~23)
    df['휠체어YN'] = df['휠체어탑승여부'].map({'Y': 1, 'N': 0})  # 이진 인코딩

    # 라벨 인코딩 (위치, 날씨)
    le_loc = LabelEncoder()
    le_weather = LabelEncoder()
    df['위치_encoded'] = le_loc.fit_transform(df['위치'])
    df['날씨_encoded'] = le_weather.fit_transform(df['날씨'])

    # 입력 변수(X)와 타겟(y) 설정
    X = df[['시간대', '위치_encoded', '날씨_encoded', '휠체어YN',
            '해당지역운행차량수', '해당지역이용자수']]
    y = df['대기시간(분)']

    # 학습/검증 데이터 분리
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # XGBoost 회귀 모델 정의 및 학습
    model = XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.1)
    model.fit(X_train, y_train)

    # 예측 성능 평가 (MAE 출력)
    print("MAE:", mean_absolute_error(y_test, model.predict(X_test)))

    # 모델 및 인코더 저장
    joblib.dump(model, "app/model/model.pkl")
    joblib.dump(le_loc, "app/model/le_loc.pkl")
    joblib.dump(le_weather, "app/model/le_weather.pkl")

    print("모델과 인코더 저장 완료!")


# ---------------------------------------------------------------------------
# ✅ 실행 진입점
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    train_model()  # 학습 함수 실행