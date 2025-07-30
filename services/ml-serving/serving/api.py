from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

# 라우터 import
from serving.routers import usage, destinations, gemini

app = FastAPI(
    title="스마트 장애인 콜택시 시스템",
    description="서울시 장애인 콜택시 실시간 이용현황 + 예측/배차 API",
    version="2.2",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 운영 시 특정 도메인으로 제한 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend())

# 라우터 등록
app.include_router(usage.router, prefix="/v2")
app.include_router(destinations.router, prefix="/v2")
app.include_router(gemini.router)
