from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator
from app.db.store import store

router = APIRouter(prefix="/settings", tags=["settings"])

class AppSettings(BaseModel):
    greenhouse_name: str = "Теплица №1"
    zone_name: str = "Зона А"
    crop: str = "Томат F1 Мерлис"
    area_ha: float = Field(1.2, gt=0, le=1000)
    timezone: Literal["Europe/Moscow (UTC+3)", "Asia/Yekaterinburg (UTC+5)", "Asia/Novosibirsk (UTC+7)", "Asia/Vladivostok (UTC+10)"] = "Europe/Moscow (UTC+3)"
    temp_unit: Literal["°C", "°F"] = "°C"
    radiation_unit: str = "µmol/m²·s"
    energy_unit: Literal["МВт·ч", "кВт·ч"] = "МВт·ч"
    
    temp_min_critical: float = Field(16.0, ge=-10, le=45)
    temp_max_critical: float = Field(28.0, ge=0, le=50)
    humidity_max_critical: float = Field(85.0, ge=1, le=100)
    vpd_min_critical: float = Field(0.3, ge=0, le=5)
    
    simulation_engine: str = "PhysicsDemoSimulationEngine"
    is_live_control_blocked: bool = True
    safety_message: str = "Передача команд оборудованию не подключена."

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.temp_min_critical >= self.temp_max_critical:
            raise ValueError("Минимум температуры должен быть меньше максимума.")
        self.is_live_control_blocked = True
        return self


@router.get("/", response_model=AppSettings)
def get_settings():
    return AppSettings.model_validate(store.get("settings", AppSettings().model_dump()))

@router.post("/", response_model=AppSettings)
def update_settings(settings: AppSettings):
    store.set("settings", settings.model_dump())
    passport = store.get("passport", {})
    passport.update(name=settings.greenhouse_name, zone=settings.zone_name, crop=settings.crop, area_ha=settings.area_ha)
    store.set("passport", passport)
    return AppSettings.model_validate(store.get("settings", AppSettings().model_dump()))
