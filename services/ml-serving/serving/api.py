from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

# 라우터 import (serving/routers/ 폴더에 있는 라우터들)
from serving.routers import usage, destinations, gemini, mock, ai_chat

# ---------------------------
# FastAPI 앱 생성
# ---------------------------
app = FastAPI(
    title="스마트 장애인 콜택시 시스템",
    description="서울시 장애인 콜택시 실시간 이용현황 + 예측/배차 API",
    version="2.2",
)

app.include_router(ai_chat.router)

# ---------------------------
# CORS 설정
# ---------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 운영 시 특정 도메인으로 제한 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# 앱 시작 시 캐시 초기화
# ---------------------------
@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend())

# ---------------------------
# 라우터 등록
# ---------------------------
# 실제 서울시 데이터 기반 API
app.include_router(usage.router, prefix="/v2")        # 통계용 API
app.include_router(destinations.router, prefix="/v2") # 목적지 추천 API
app.include_router(gemini.router)                     # Gemini 기반 AI 채팅 API

# 더미(Mock) 데이터용 API (동적 랜덤 생성)
app.include_router(mock.router, prefix="/mock")
