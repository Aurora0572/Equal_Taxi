# training/data_generator.py

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

def generate_dummy_data(n_rows=5000):
    """
    대기시간 예측을 위한 더미 데이터 생성
    """
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
        '탑승시각', '위치', '날씨', '휠체어탑승여부', '대기시간(분)', '해당지역운행차량수', '해당지역이용자수'
    ])
