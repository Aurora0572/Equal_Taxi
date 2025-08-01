# --------------------------------------------------
# Dockerfile   (infra/Dockerfile)
# --------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# ▶ 시스템 패키지가 필요 없다면 build-essential 삭제해도 됩니다
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY services/ml-serving/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ────────────────────────────────────────────────
# ① 애플리케이션 코드
COPY services/ml-serving/serving ./serving

# ② 모델 파일  👉  **serving/app/model** 로 넣어준다 (🔄 수정)
COPY services/ml-serving/app/model ./serving/app/model
# ────────────────────────────────────────────────

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["uvicorn", "serving.api:app", "--host", "0.0.0.0", "--port", "8000"]
