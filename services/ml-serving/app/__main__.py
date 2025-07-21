from __future__ import annotations  # Python의 미래 호환성 위한 선언 (예: forward reference 지원)

# uvicorn: ASGI 서버. FastAPI 앱을 실행하는 데 사용
import uvicorn

# app: FastAPI 애플리케이션 인스턴스 (api.py 내부 정의)
from .api import app


# ✅ 현재 파일이 직접 실행되는 경우에만 아래 코드 실행
# (다른 파일에서 import 될 때는 실행되지 않음)
if __name__ == "__main__":
    # ✅ uvicorn을 통해 FastAPI 앱 실행
    # host: 0.0.0.0 은 외부 접근 허용 (Docker 환경 등에서 사용)
    # port: 기본 포트 8000번 사용
    uvicorn.run(app, host="0.0.0.0", port=8000)