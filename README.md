services/
└─ ml-serving/
   ├─ app/
   │  └─ serving/
   │     ├─ api.py                 # FastAPI 앱 초기화 & 라우터 등록 (엔트리포인트)
   │     │
   │     ├─ routers/               # 엔드포인트 관리
   │     │  ├─ usage.py            # /v2/usage
   │     │  ├─ destinations.py     # /v2/best_destinations
   │     │  └─ gemini.py           # /ask_gemini
   │     │
   │     ├─ services/              # 외부 API 호출 및 비즈니스 로직
   │     │  ├─ seoul_api.py        # 서울시 콜택시 API 처리
   │     │  ├─ tmap_api.py         # Tmap ETA 처리
   │     │  └─ gemini_service.py   # Gemini 연동 처리
   │     │
   │     ├─ constants.py           # 상수 (BASE_URL, DEFAULT_DATE 등)
   │     ├─ dispatch.py            # 배차 로직 (추후 ML 연결)
   │     ├─ models.py              # DB 모델 또는 ML 모델 클래스
   │     ├─ schemas.py             # Pydantic 스키마
   │     ├─ utils.py               # 공통 유틸 함수 (env 로드 등)
   │     └─ analysis.py            # 데이터 분석/전처리 (추가 알고리즘용)
   │
   ├─ training/                    # 모델 학습 관련 (기존 그대로)
   ├─ venv/                        # 가상환경 (기존 그대로)
   ├─ .env
   ├─ debug_response.html
   └─ requirements.txt
