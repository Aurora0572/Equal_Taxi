import os
from pathlib import Path

def get_env(key: str, default: str = None) -> str:
    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"환경 변수 {key}가 설정되지 않았습니다.")
    return value

def model_dir() -> Path:
    """
    모델 파일이 저장된 경로를 반환.
    """
    return Path(__file__).resolve().parents[1] / "app" / "model"
