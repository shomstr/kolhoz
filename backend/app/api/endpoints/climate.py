from fastapi import APIRouter
from typing import List
from app.models.schemas import ClimateCurrent, ClimateHistoryPoint
from app.services.data_service import DataService

router = APIRouter(prefix="/climate", tags=["climate"])
data_service = DataService()

@router.get("/current", response_model=ClimateCurrent)
def get_current_climate():
    return data_service.get_current_climate()

@router.get("/history-24h", response_model=List[ClimateHistoryPoint])
def get_climate_history_24h():
    return data_service.get_climate_history_24h()

@router.get("/zones")
def get_zones():
    current = data_service.get_current_climate()
    return [{"id": "zone_a", "name": current.zone_name, "crop": current.crop, "area": f"{current.area_ha} га", "status": current.status, "temp": current.temperature, "humidity": current.humidity, "co2": current.co2, "light": current.light}]
