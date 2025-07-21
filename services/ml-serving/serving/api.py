# FastAPI 웹 프레임워크 및 예외 처리 모듈 임포트
from fastapi import FastAPI, HTTPException

# dispatch.py에 정의된 라우터 객체 가져오기 (스마트 배차 관련 API 포함)
from .dispatch import router as dispatch_router

# 머신러닝 모델 자산 로드 함수 (예: 대기시간 예측 모델)
from .utils import load_model_assets

# 예측 입력 스키마 (필요시 예측 API 등에서 사용)
from .schemas import InputData

# 예측 입력용 DataFrame 구성 함수 (확장 가능)
from .utils import build_predict_dataframe


# ✅ FastAPI 애플리케이션 객체 생성
# ASGI 서버에서 실행될 주 앱 정의
app = FastAPI(
    title="스마트 장애인 콜택시 시스템",         # API 문서 제목
    description="대기시간 예측 + 스마트 배차 API",  # 문서 설명
    version="2.0",                            # 버전 정보
)


# ✅ dispatch.py의 라우터 등록 (API 라우팅 구성)
# /smart_dispatch, /batch_optimize 등 등록
app.include_router(dispatch_router)


# ✅ 서버 시작 시 모델 등 자산 미리 로딩
# 대기시간 예측 등에 사용되는 ML 모델 및 인코더
model, le_loc, le_weather = load_model_assets()


# ✅ 루트 경로 "/" 접속 시 간단한 안내 메시지 제공
@app.get("/")
def root():
    """
    기본 루트 확인용 엔드포인트.
    서버가 정상 실행 중인지 확인할 수 있음.
    """
    return {
        "message": "🚕 스마트 장애인 콜택시 API 서버 동작 중입니다.",
        "endpoints": [
            "/smart_dispatch/",       # 스마트 배차 요청
            "/batch_optimize/",       # 다중 요청 최적화
            "/system_status/",        # 시스템 상태 조회
            "/update_profile/",       # 사용자 프로필 갱신
        ]
    }