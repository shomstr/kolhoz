from fastapi import APIRouter, HTTPException
from typing import List
from uuid import uuid4
from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.schemas import SimulationRequest, SimulationResult, ScenarioEquipmentParams
from app.services.simulation_engine import PhysicsDemoSimulationEngine
from app.services.data_service import DataService
from app.services.economics_service import EconomicsService
from app.db.store import store

router = APIRouter(prefix="/experiments", tags=["experiments"])
engine = PhysicsDemoSimulationEngine()
data_service = DataService()
economics_service = EconomicsService()

@router.post("/simulate", response_model=SimulationResult)
def run_simulation(request: SimulationRequest):
    initial_state = data_service.get_current_climate()
    tariffs = economics_service.get_tariffs()
    result = engine.simulate(request=request, initial_state=initial_state, tariffs=tariffs)
    result.id = f"exp-{uuid4().hex[:10]}"
    result.created_at = datetime.now(ZoneInfo("Europe/Moscow")).isoformat()
    result.initial_state = initial_state
    result.request = request
    result.parameters = request.custom_scenario
    result.source_name = initial_state.source_name
    history = store.get("experiment_history", [])
    store.set("experiment_history", [result.model_dump(), *history])
    return result

@router.get("/presets")
def get_presets():
    return {
        "baseline": ScenarioEquipmentParams(
            name="Базовый сценарий",
            heating_temp=22.0,
            vent_min_open=10.0,
            screen_mode="auto_day_night",
            lighting_intensity=300.0,
            co2_target=800.0,
            night_temp_drop=2.0
        ),
        "eco": ScenarioEquipmentParams(
            name="Экономичный сценарий",
            heating_temp=20.5,
            vent_min_open=15.0,
            screen_mode="energy_save",
            lighting_intensity=250.0,
            co2_target=750.0,
            night_temp_drop=3.0
        ),
        "aggressive": ScenarioEquipmentParams(
            name="Агрессивный сценарий",
            heating_temp=23.5,
            vent_min_open=8.0,
            screen_mode="auto_day_night",
            lighting_intensity=450.0,
            co2_target=900.0,
            night_temp_drop=1.0
        )
    }

@router.get("/scenarios", response_model=List[ScenarioEquipmentParams])
def get_saved_scenarios():
    saved = store.get("saved_scenarios", [])
    return [ScenarioEquipmentParams.model_validate(item) for item in saved]

@router.post("/scenarios", response_model=ScenarioEquipmentParams)
def save_scenario(scenario: ScenarioEquipmentParams):
    saved = store.get("saved_scenarios", [])
    normalized_name = scenario.name.strip().casefold()
    saved = [item for item in saved if str(item.get("name", "")).strip().casefold() != normalized_name]
    saved.insert(0, scenario.model_dump())
    store.set("saved_scenarios", saved)
    return scenario

@router.get("/history", response_model=List[SimulationResult])
def experiment_history():
    return store.get("experiment_history", [])

@router.delete("/scenarios/{name}")
def delete_scenario(name: str):
    saved = store.get("saved_scenarios", [])
    store.set("saved_scenarios", [item for item in saved if item["name"] != name])
    return {"deleted": name}

@router.post("/preview", response_model=SimulationResult)
def preview_simulation(request: SimulationRequest):
    result = engine.simulate(request, data_service.get_current_climate(), economics_service.get_tariffs())
    result.request = request
    result.parameters = request.custom_scenario
    result.initial_state = data_service.get_current_climate()
    result.source_name = result.initial_state.source_name
    return result
