import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor
import joblib
from pathlib import Path

# ✅ 디렉토리 먼저 생성
Path("app/model").mkdir(parents=True, exist_ok=True)

# 더미 데이터 생성
def generate_data(n_rows=5000):
    start_time = datetime(2024, 7, 1, 6)
    locations = ['강남', '종로', '노원', '송파', '영등포', '성동']
    weather_types = ['맑음', '흐림', '비', '눈']

    data = []
    for i in range(n_rows):
        timestamp = start_time + timedelta(minutes=15 * i)
        location = random.choice(locations)
        weather = random.choice(weather_types)
        wheelchair = random.choice(['Y', 'N'])
        waiting_time = max(0, int(np.random.normal(10 if weather == '맑음' else 20, 5)))
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

# 학습 함수
def train_model():
    df = generate_data()
    df['시간대'] = pd.to_datetime(df['탑승시각']).dt.hour
    df['휠체어YN'] = df['휠체어탑승여부'].map({'Y': 1, 'N': 0})

    le_loc = LabelEncoder()
    le_weather = LabelEncoder()
    df['위치_encoded'] = le_loc.fit_transform(df['위치'])
    df['날씨_encoded'] = le_weather.fit_transform(df['날씨'])

    X = df[['시간대', '위치_encoded', '날씨_encoded', '휠체어YN',
            '해당지역운행차량수', '해당지역이용자수']]
    y = df['대기시간(분)']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.1)
    model.fit(X_train, y_train)

    print("MAE:", mean_absolute_error(y_test, model.predict(X_test)))

    joblib.dump(model, "app/model/model.pkl")
    joblib.dump(le_loc, "app/model/le_loc.pkl")
    joblib.dump(le_weather, "app/model/le_weather.pkl")

    print("모델과 인코더 저장 완료!")

# 메인 실행
if __name__ == "__main__":
    train_model()
