from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field

class ClimateTargetRanges(BaseModel):
    temp_min: float = 22.0
    temp_max: float = 24.0
    humidity_min: float = 60.0
    humidity_max: float = 75.0
    co2_min: float = 700.0
    co2_max: float = 900.0
    light_min: float = 300.0
    light_max: float = 400.0

class ClimateCurrent(BaseModel):
    available_metrics: List[str] = ["temperature", "humidity", "co2", "light"]
    source_kind: str = "sample"
    source_name: str = "Пример журнала"
    timezone: str = "Europe/Moscow"
    temperature: float = 21.8
    humidity: float = 67.0
    co2: float = 810.0
    light: float = 320.0
    outdoor_temp: float = 4.2
    outdoor_humidity: Optional[float] = None
    outdoor_solar: float = 180.0 # W/m2
    targets: ClimateTargetRanges = Field(default_factory=ClimateTargetRanges)
    status: str = "DEMO"
    status_text: str = "Демонстрационные значения — датчики не подключены"
    last_updated: str = "2026-10-10 14:25"
    greenhouse_name: str = "Теплица №1"
    zone_id: str = "zone_a"
    zone_name: str = "Зона А"
    crop: str = "Томат"
    area_ha: float = 1.2
    cycle: str = "Зимний цикл 2026–2027"

class ClimateHistoryPoint(BaseModel):
    timestamp: Optional[str] = None
    time: str
    fact_temp: Optional[float] = None
    forecast_temp: Optional[float] = None
    target_temp_min: float = 22.0
    target_temp_max: float = 24.0
    
    fact_humidity: Optional[float] = None
    forecast_humidity: Optional[float] = None
    target_humidity_min: float = 60.0
    target_humidity_max: float = 75.0
    
    fact_co2: Optional[float] = None
    forecast_co2: Optional[float] = None
    target_co2_min: float = 700.0
    target_co2_max: float = 900.0
    
    fact_light: Optional[float] = None
    forecast_light: Optional[float] = None
    target_light_min: float = 300.0
    target_light_max: float = 400.0
    
    outdoor_temp: Optional[float] = None
    outdoor_humidity: Optional[float] = None
    outdoor_solar: Optional[float] = None
    heating_valve_pct: Optional[float] = None
    vent_open_pct: Optional[float] = None
    screens_pct: Optional[float] = None
    lamps_pct: Optional[float] = None
    is_gap: bool = False

class ScenarioEquipmentParams(BaseModel):
    name: str = Field("Пользовательский", min_length=1, max_length=100)
    heating_temp: float = Field(22.0, ge=16.0, le=28.0, description="Температура уставки, °C")
    vent_min_open: float = Field(10.0, ge=0.0, le=100.0, description="Минимальное открытие вентиляции, %")
    screen_mode: Literal["auto_day_night", "closed", "open", "energy_save"] = Field("auto_day_night", description="Режим экранов: auto_day_night, closed, open, energy_save")
    lighting_intensity: float = Field(300.0, ge=0.0, le=800.0, description="Интенсивность досветки, µmol/m²·s")
    co2_target: float = Field(800.0, ge=400.0, le=1500.0, description="Целевой уровень CO2, ppm")
    night_temp_drop: float = Field(2.0, ge=0.0, le=6.0, description="Ночное понижение уставки, °C")

class SimulationRequest(BaseModel):
    horizon_hours: int = Field(24, ge=6, le=24, description="Горизонт моделирования: от 6 до 24 часов")
    custom_scenario: Optional[ScenarioEquipmentParams] = None
    preset_baseline: Optional[ScenarioEquipmentParams] = None
    preset_eco: Optional[ScenarioEquipmentParams] = None
    preset_aggressive: Optional[ScenarioEquipmentParams] = None

class SimulationSeriesPoint(BaseModel):
    baseline_power_kw: Optional[float] = None
    custom_power_kw: Optional[float] = None
    aggressive_power_kw: Optional[float] = None
    timestamp: Optional[str] = None
    time: str
    baseline_temp: float
    eco_temp: float
    aggressive_temp: float
    custom_temp: Optional[float] = None
    fact_temp: Optional[float] = None
    
    baseline_humidity: float
    eco_humidity: float
    aggressive_humidity: float
    custom_humidity: Optional[float] = None
    
    baseline_co2: float
    eco_co2: float
    aggressive_co2: float
    custom_co2: Optional[float] = None

class ScenarioKpi(BaseModel):
    scenario_name: str
    heat_mwh: float
    heat_diff_pct: float
    elec_mwh: float
    elec_diff_pct: float
    total_cost_rub: float
    cost_diff_rub: float
    cost_diff_pct: float
    violations: List[str] = []
    status_badge: str = "Норма"

class SimulationResult(BaseModel):
    request: Optional[SimulationRequest] = None
    id: Optional[str] = None
    created_at: Optional[str] = None
    initial_state: Optional[ClimateCurrent] = None
    parameters: Optional[ScenarioEquipmentParams] = None
    source_name: str = "Пример журнала"
    is_demo: bool = True
    demo_disclaimer: str = "DEMO: Упрощённые эвристические расчёты для демонстрации интерфейса. Модель не калибрована и не проверена на объекте. Прямое управление отключено."
    model_version: str = "v1.2.4-demo"
    horizon_hours: int = 24
    series: List[SimulationSeriesPoint]
    baseline_kpi: ScenarioKpi
    eco_kpi: ScenarioKpi
    aggressive_kpi: ScenarioKpi
    custom_kpi: Optional[ScenarioKpi] = None
    model_assumptions: List[str] = [
        "Все варианты используют один срез исходных данных и общий синтетический профиль погоды.",
        "Климатические ряды упрощённо сглаживаются к заданным уставкам; динамика не калибрована по измерениям теплицы.",
        "Тепло оценивается по площади и мощности из паспорта и приближённым потерям; электричество — по интенсивности досветки.",
        "Стоимость сценария включает только тепло и электричество; расход CO₂ не рассчитывается.",
        "Объёмы, тарифы и результаты не подтверждены счётчиками или испытаниями на объекте."
    ]

class ColumnMapping(BaseModel):
    light_col: Optional[str] = "ppfd"
    vent_open_col: Optional[str] = "vent_open"
    screens_col: Optional[str] = "screen_pct"
    lamps_col: Optional[str] = "lighting_pct"
    timestamp_col: str = "timestamp"
    temp_air_col: str = "temp_air"
    humidity_col: str = "humidity"
    co2_col: Optional[str] = "co2"
    heating_valve_col: Optional[str] = "heating_valve"
    solar_col: Optional[str] = "solar_radiation"
    outdoor_temp_col: Optional[str] = "outdoor_temp"

class DataQualityReport(BaseModel):
    applied: bool = False
    valid_rows: int = 0
    filename: str
    total_rows: int
    missing_rate_pct: float
    unit_errors_pct: float
    sample_interval_min: int
    outliers_pct: float
    quality_status: str # "EXCELLENT", "ACCEPTABLE", "WARNING"
    detected_columns: List[str]
    column_mapping: ColumnMapping
    preview_rows: List[Dict[str, Any]]
    validation_messages: List[str]

class GreenhousePassport(BaseModel):
    name: str = "Теплица №1"
    zone: str = "Зона А"
    crop: str = "Томат индетерминантный (F1 Мерлис)"
    area_ha: float = Field(1.2, gt=0, le=1000)
    glass_type: str = "Одинарное флоат-стекло 4 мм (коэфф. светопропускания 89%)"
    screen_type: str = "Энергосберегающий термоэкран Luxous 1147 FR"
    heating_capacity_mw: float = Field(4.8, ge=0, le=1000)
    lighting_capacity_w_m2: float = Field(120.0, ge=0, le=2000)
    ventilation_type: str = "Коньковая непрерывная с электроприводом"
    co2_system: str = "Дозирование отходящих газов котельной (LUX 800-1200)"
    sowing_date: str = "2026-08-15"
    planned_yield_kg_m2: float = Field(68.5, ge=0)

class TariffConfig(BaseModel):
    implementation_cost_rub: float = Field(0, ge=0)
    heat_rate_rub_mwh: float = Field(2100.0, ge=0)
    elec_day_rate_rub_mwh: float = Field(4850.0, ge=0)
    elec_night_rate_rub_mwh: float = Field(2450.0, ge=0)
    co2_rate_rub_kg: float = Field(3.5, ge=0)

class EconomicsSummary(BaseModel):
    period: str = "month"
    tariffs: TariffConfig
    eco_savings_pct_heat: float = 0.0
    eco_savings_pct_elec: float = 0.0
    eco_monthly_savings_rub: float = 0.0
    
    baseline_monthly_cost_rub: float = 0.0
    eco_monthly_cost_rub: float = 0.0
    aggressive_monthly_cost_rub: float = 0.0
    
    payback_months_min: Optional[int] = None
    payback_months_max: Optional[int] = None
    expected_economy_min_rub: int = 0
    expected_economy_max_rub: int = 0
    
    cost_structure: List[Dict[str, Any]]
    resource_breakdown: List[Dict[str, Any]]
    historical_confirmed_savings_rub: float = 0.0
    modeled_projected_savings_rub: float = 0.0

class DecisionRecord(BaseModel):
    experiment_id: Optional[str] = None
    id: str
    timestamp: str
    author: str = "Агроном"
    scenario_name: str
    decision_type: str = "Внедрение экономичного режима"
    expected_effect: str
    status: str = "Принято"
    parameters_summary: str
    notes: Optional[str] = None

class CreateDecisionRequest(BaseModel):
    experiment_id: Optional[str] = None
    scenario_name: str
    parameters_summary: str
    expected_effect: str
    notes: Optional[str] = None
    author: Optional[str] = "Агроном"
