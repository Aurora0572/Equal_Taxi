"""
serving/core/utils.py
공통 유틸리티 모음
"""

import os
from pathlib import Path


# ────────────────────────────────────────────────
# 1. 환경 변수 읽기
# ────────────────────────────────────────────────
def get_env(key: str, default: str | None = None) -> str:
    """
    .env 또는 시스템 환경 변수에서 값을 읽어온다.

    Parameters
    ----------
    key : str
        환경 변수 이름
    default : str | None
        기본값. 기본값이 없고 변수도 없으면 RuntimeError 발생
    """
    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"환경 변수 '{key}'가 설정되지 않았습니다.")
    return value


# ────────────────────────────────────────────────
# 2. 모델 경로 도우미
# ────────────────────────────────────────────────
def model_dir() -> Path:
    """
    Dockerfile 에서 모델을 <프로젝트>/serving/app/model 로 복사하도록
    구성했으므로 해당 경로를 반환한다.
    """
    # utils.py 위치: <프로젝트>/serving/core/utils.py
    # parents[1]  : <프로젝트>/serving
    # app/model   : <프로젝트>/serving/app/model
    return Path(__file__).resolve().parents[1] / "app" / "model"
