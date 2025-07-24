import sys
from pathlib import Path

# 최상위 디렉토리 (ml-serving) 를 모듈 경로에 추가
sys.path.append(str(Path(__file__).resolve().parents[1]))

from serving.api import app  # ✅ 이렇게 수정해야 제대로 불러옴
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
