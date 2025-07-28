# routes/best_destinations.py

from fastapi import APIRouter, HTTPException, Query
from services.data_pipeline.best_destinations_loader import load_best_destinations

router = APIRouter()

@router.get("/best_destinations")
def get_best_destinations(sDate: str = Query(..., description="YYYYMMDD 형식")):
    try:
        df = load_best_destinations(sDate)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
