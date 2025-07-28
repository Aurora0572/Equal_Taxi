from fastapi import APIRouter, HTTPException
from services.data_pipeline.usage_loader import load_usage_from_api

router = APIRouter()

@router.get("/usage")
def get_usage(date: str):
    try:
        df = load_usage_from_api(date)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
