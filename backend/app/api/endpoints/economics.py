from fastapi import APIRouter, Query
from app.models.schemas import EconomicsSummary, TariffConfig
from app.services.economics_service import EconomicsService

router = APIRouter(prefix="/economics", tags=["economics"])
service = EconomicsService()

@router.get("/summary", response_model=EconomicsSummary)
def get_economics_summary(period: str = Query("month", pattern="^(month|year|quarter)$")):
    return service.get_summary(period=period)

@router.get("/tariffs", response_model=TariffConfig)
def get_tariffs():
    return service.get_tariffs()

@router.post("/tariffs", response_model=TariffConfig)
def update_tariffs(tariffs: TariffConfig):
    return service.update_tariffs(tariffs)
