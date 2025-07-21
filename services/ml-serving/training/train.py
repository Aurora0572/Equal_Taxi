from pathlib import Path
from training.data_generator import generate_dummy_data

# ✅ 모델 저장 경로 설정 (절대 경로)
MODEL_DIR = Path(__file__).resolve().parents[1] / "app" / "model"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

def train_model():
    df = generate_dummy_data()
    df['시간대'] = pd.to_datetime(df['탑승시각']).dt.hour
    df['휠체어YN'] = df['휠체어탑승여부'].map({'Y': 1, 'N': 0})

    from sklearn.preprocessing import LabelEncoder
    le_loc = LabelEncoder()
    le_weather = LabelEncoder()
    df['위치_encoded'] = le_loc.fit_transform(df['위치'])
    df['날씨_encoded'] = le_weather.fit_transform(df['날씨'])

    from sklearn.model_selection import train_test_split
    X = df[['시간대', '위치_encoded', '날씨_encoded', '휠체어YN',
            '해당지역운행차량수', '해당지역이용자수']]
    y = df['대기시간(분)']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    from xgboost import XGBRegressor
    model = XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.1)
    model.fit(X_train, y_train)

    from sklearn.metrics import mean_absolute_error
    print("MAE:", mean_absolute_error(y_test, model.predict(X_test)))

    # ✅ 경로 안정적으로 저장
    import joblib
    joblib.dump(model, MODEL_DIR / "model.pkl")
    joblib.dump(le_loc, MODEL_DIR / "le_loc.pkl")
    joblib.dump(le_weather, MODEL_DIR / "le_weather.pkl")

    print("✅ 모델과 인코더 저장 완료:", MODEL_DIR)

if __name__ == "__main__":
    train_model()