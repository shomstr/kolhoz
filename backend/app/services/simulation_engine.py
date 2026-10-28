import math
from abc import ABC, abstractmethod
from app.db.store import store
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Any, Optional
from app.models.schemas import (
    SimulationRequest,
    SimulationResult,
    SimulationSeriesPoint,
    ScenarioEquipmentParams,
    ScenarioKpi,
    ClimateCurrent,
    TariffConfig,
)

class BaseSimulationEngine(ABC):
    """
    Абстрактный базовый класс для движков моделирования микроклимата теплицы.
    Позволяет подключить реальную модель машинного обучения / ODE / CFD через API.
    """
    @abstractmethod
    def simulate(
        self,
        request: SimulationRequest,
        initial_state: ClimateCurrent,
        tariffs: Optional[TariffConfig] = None
    ) -> SimulationResult:
        pass


class PhysicsDemoSimulationEngine(BaseSimulationEngine):
    """
    Упрощённая демонстрационная эвристика для интерфейса сценариев.

    Использует фиксированные параметры площади/теплопередачи и синтетическую погоду.
    Климатические ряды плавно приближаются к выбранным уставкам, а затраты
    считаются по приблизительным тепловым потерям и мощности досветки. Модель
    не калибрована, не проверена на объекте и не должна трактоваться как прогноз.
    """

    def __init__(self):
        self.greenhouse_area_m2 = 12000.0  # 1.2 га
        self.volume_m3 = 12000.0 * 5.5     # высота в коньке ~5.5 м
        self.glass_u_val = 6.2             # Вт/(м²·К) без экрана
        self.screen_u_val = 3.8            # Вт/(м²·К) с закрытым экраном
        self.version = "balance-1.3"

    def _generate_weather_profile(self, horizon_hours: int, start_hour: int = 0) -> List[Dict[str, float]]:
        """Генерация повторяемого синтетического суточного профиля погоды."""
        weather = []
        # Горизонт до 24 часов возвращает почасовые точки.
        step_hours = max(1, horizon_hours // 24)
        total_steps = horizon_hours // step_hours
        
        for i in range(total_steps):
            hour = (start_hour + i * step_hours) % 24
            # Температура наружная: ночью холоднее (2..3°C), днем теплее (5..7°C)
            diurnal_temp = 3.0 + 3.0 * math.sin((hour - 8) * math.pi / 12)
            # Солнечная радиация (Вт/м²): с 8:00 до 17:00
            if 8 <= hour <= 17:
                solar_rad = max(0.0, 280.0 * math.sin((hour - 8) * math.pi / 9))
            else:
                solar_rad = 0.0
            
            outdoor_rh = 85.0 - 15.0 * (solar_rad / 280.0) if solar_rad > 0 else 88.0
            weather.append({
                "step": i,
                "hour": hour,
                "hour_str": f"{hour:02d}:00",
                "temp_out": round(diurnal_temp, 1),
                "solar_w_m2": round(solar_rad, 1),
                "outdoor_rh": round(outdoor_rh, 1)
            })
        return weather

    def _simulate_single_scenario(
        self,
        params: ScenarioEquipmentParams,
        weather: List[Dict[str, float]],
        tariffs: TariffConfig,
        initial_state: ClimateCurrent,
    ) -> Dict[str, Any]:
        passport = store.get("passport", {})
        limits = store.get("settings", {})
        area_m2 = float(passport.get("area_ha", limits.get("area_ha", 1.2))) * 10000
        volume_m3 = area_m2 * 5.5
        heat_capacity = float(passport.get("heating_capacity_mw", 4.8)) * 1000000
        heat_mwh_total = 0.0
        elec_mwh_total = 0.0
        total_cost = 0.0

        temps = []
        humidities = []
        co2s = []
        power_series = []
        violations = []
        current_temp = initial_state.temperature
        current_humidity = initial_state.humidity
        current_co2 = initial_state.co2 if "co2" in initial_state.available_metrics else 800.0

        for w in weather:
            hour = w["hour"]
            is_day = 8 <= hour <= 20
            t_out = w["temp_out"]
            solar = w["solar_w_m2"]

            # Целевая температура с учётом ночного спада
            target_t = params.heating_temp if is_day else (params.heating_temp - params.night_temp_drop)

            # Экраны: закрыты ночью в режиме авто
            screen_closed = (not is_day) if params.screen_mode == "auto_day_night" else (params.screen_mode != "open")
            u_current = self.screen_u_val if screen_closed else self.glass_u_val

            # Теплопотери через ограждения: U * A * deltaT (Вт)
            heat_loss_watts = u_current * (area_m2 * 1.25) * max(0.0, target_t - t_out)

            # Вентиляционные теплопотери:
            # Упрощённый коэффициент DEMO: 1% открытия задаёт 0.12 обмена в час.
            air_changes_per_hr = max(0.3, params.vent_min_open * 0.12)
            # rho * Cp air ~ 1200 Дж/(м³·К) = 0.333 Вт·ч/(м³·К)
            vent_heat_loss_watts = air_changes_per_hr * volume_m3 * 0.333 * max(0.0, target_t - t_out)

            # Поступление тепла от солнца и досветки
            solar_heat_gain = 0.70 * solar * area_m2 # ~70% тепла от солнца
            
            # Досветка работает в дневное/продленное время (06:00 - 22:00)
            lamps_on = 6 <= hour <= 22 and params.lighting_intensity > 0
            lamp_power_watts = (params.lighting_intensity / 2.5) * area_m2 if lamps_on else 0.0
            power_series.append(round(lamp_power_watts / 1000, 2))
            lamp_heat_gain = lamp_power_watts * 0.65 # ~65% мощности ламп переходит в конвективное тепло

            # Необходимое отопление (Вт)
            required_heating_watts = min(heat_capacity, max(0.0, heat_loss_watts + vent_heat_loss_watts - solar_heat_gain - lamp_heat_gain))

            # Шаг времени (1 час)
            heat_kwh = required_heating_watts / 1000.0
            heat_mwh = heat_kwh / 1000.0
            heat_mwh_total += heat_mwh

            elec_kwh = lamp_power_watts / 1000.0
            elec_mwh = elec_kwh / 1000.0
            elec_mwh_total += elec_mwh

            # Стоимость часа
            elec_rate = tariffs.elec_day_rate_rub_mwh if (7 <= hour < 23) else tariffs.elec_night_rate_rub_mwh
            cost_hour = heat_mwh * tariffs.heat_rate_rub_mwh + elec_mwh * elec_rate
            total_cost += cost_hour

            # Динамика температуры воздуха
            temp_equilibrium = target_t + (0.4 if solar > 200 else -0.2)
            t_in = current_temp + 0.65 * (temp_equilibrium - current_temp)
            current_temp = t_in
            temps.append(round(t_in, 1))

            # Упрощённая целевая влажность зависит от вентиляции и ночного режима экранов.
            base_rh = 70.0
            if params.vent_min_open > 20:
                rh_equilibrium = max(55.0, base_rh - (params.vent_min_open - 20) * 0.4)
            else:
                rh_equilibrium = min(88.0, base_rh + (20 - params.vent_min_open) * 0.6)
            
            if screen_closed and not is_day:
                rh_equilibrium += 4.0 # Под экраном влажность выше
            rh_in = current_humidity + 0.6 * (rh_equilibrium - current_humidity)
            current_humidity = rh_in
            humidities.append(round(rh_in, 1))

            # Динамика CO2
            if lamps_on:
                co2_equilibrium = params.co2_target - (params.vent_min_open * 1.5)
            else:
                co2_equilibrium = min(params.co2_target + 50.0, 950.0)
            co2_in = current_co2 + 0.65 * (co2_equilibrium - current_co2)
            current_co2 = co2_in
            co2s.append(round(co2_in, 0))

            saturation = .6108 * math.exp(17.27 * t_in / (t_in + 237.3))
            vpd = saturation * (1 - rh_in / 100)
            candidates = []
            if t_in < limits.get("temp_min_critical", 16):
                candidates.append("Температура ниже допустимого минимума")
            if t_in > limits.get("temp_max_critical", 28):
                candidates.append("Температура выше допустимого максимума")
            if rh_in > limits.get("humidity_max_critical", 85):
                candidates.append("Влажность выше допустимого максимума")
            if vpd < limits.get("vpd_min_critical", .3):
                candidates.append("VPD ниже допустимого минимума")
            violations.extend(message for message in candidates if message not in violations)

        return {
            "heat_mwh": round(heat_mwh_total, 4),
            "elec_mwh": round(elec_mwh_total, 4),
            "total_cost_rub": round(total_cost, 0),
            "temps": temps,
            "humidities": humidities,
            "co2s": co2s,
            "power_series": power_series,
            "violations": violations
        }

    def simulate(
        self,
        request: SimulationRequest,
        initial_state: ClimateCurrent,
        tariffs: Optional[TariffConfig] = None
    ) -> SimulationResult:
        if tariffs is None:
            tariffs = TariffConfig()

        start_time = pd.to_datetime(initial_state.last_updated, errors="coerce", dayfirst=True)
        if pd.isna(start_time):
            start_time = pd.Timestamp.now(tz="UTC")
        if start_time.tzinfo is None:
            start_time = start_time.tz_localize(store.get("settings", {}).get("timezone", "Europe/Moscow").split(" ")[0])
        start_time = start_time.tz_convert(store.get("settings", {}).get("timezone", "Europe/Moscow").split(" ")[0])
        weather = self._generate_weather_profile(request.horizon_hours, start_time.hour)

        # Сценарии по умолчанию в соответствии с референсом
        baseline_params = request.preset_baseline or ScenarioEquipmentParams(
            name="Базовый",
            heating_temp=22.0,
            vent_min_open=10.0,
            screen_mode="auto_day_night",
            lighting_intensity=300.0,
            co2_target=800.0,
            night_temp_drop=2.0
        )

        eco_params = request.preset_eco or ScenarioEquipmentParams(
            name="Экономичный",
            heating_temp=20.5,
            vent_min_open=15.0,
            screen_mode="energy_save",
            lighting_intensity=250.0,
            co2_target=750.0,
            night_temp_drop=3.0
        )

        aggressive_params = request.preset_aggressive or ScenarioEquipmentParams(
            name="Агрессивный",
            heating_temp=23.5,
            vent_min_open=8.0,
            screen_mode="auto_day_night",
            lighting_intensity=450.0,
            co2_target=900.0,
            night_temp_drop=1.0
        )

        res_baseline = self._simulate_single_scenario(baseline_params, weather, tariffs, initial_state)
        res_eco = self._simulate_single_scenario(eco_params, weather, tariffs, initial_state)
        res_aggressive = self._simulate_single_scenario(aggressive_params, weather, tariffs, initial_state)

        # Вычисление относительных разниц (%)
        base_heat = res_baseline["heat_mwh"]
        base_elec = res_baseline["elec_mwh"]
        base_cost = res_baseline["total_cost_rub"]

        eco_kpi = ScenarioKpi(
            scenario_name="Экономичный",
            heat_mwh=res_eco["heat_mwh"],
            heat_diff_pct=round(((res_eco["heat_mwh"] - base_heat) / (base_heat or 1.0)) * 100.0, 1),
            elec_mwh=res_eco["elec_mwh"],
            elec_diff_pct=round(((res_eco["elec_mwh"] - base_elec) / (base_elec or 1.0)) * 100.0, 1),
            total_cost_rub=res_eco["total_cost_rub"],
            cost_diff_rub=round(res_eco["total_cost_rub"] - base_cost, 0),
            cost_diff_pct=round(((res_eco["total_cost_rub"] - base_cost) / (base_cost or 1.0)) * 100.0, 1),
            violations=res_eco["violations"],
            status_badge="Есть нарушения" if res_eco["violations"] else "В пределах порогов"
        )

        aggressive_kpi = ScenarioKpi(
            scenario_name="Агрессивный",
            heat_mwh=res_aggressive["heat_mwh"],
            heat_diff_pct=round(((res_aggressive["heat_mwh"] - base_heat) / (base_heat or 1.0)) * 100.0, 1),
            elec_mwh=res_aggressive["elec_mwh"],
            elec_diff_pct=round(((res_aggressive["elec_mwh"] - base_elec) / (base_elec or 1.0)) * 100.0, 1),
            total_cost_rub=res_aggressive["total_cost_rub"],
            cost_diff_rub=round(res_aggressive["total_cost_rub"] - base_cost, 0),
            cost_diff_pct=round(((res_aggressive["total_cost_rub"] - base_cost) / (base_cost or 1.0)) * 100.0, 1),
            violations=res_aggressive["violations"],
            status_badge="Высокий расход"
        )

        baseline_kpi = ScenarioKpi(
            scenario_name="Базовый",
            heat_mwh=res_baseline["heat_mwh"],
            heat_diff_pct=0.0,
            elec_mwh=res_baseline["elec_mwh"],
            elec_diff_pct=0.0,
            total_cost_rub=res_baseline["total_cost_rub"],
            cost_diff_rub=0.0,
            cost_diff_pct=0.0,
            violations=res_baseline["violations"],
            status_badge="Базовый уровень"
        )

        custom_kpi = None
        res_custom = None
        if request.custom_scenario:
            res_custom = self._simulate_single_scenario(request.custom_scenario, weather, tariffs, initial_state)
            custom_kpi = ScenarioKpi(
                scenario_name=request.custom_scenario.name or "Пользовательский",
                heat_mwh=res_custom["heat_mwh"],
                heat_diff_pct=round(((res_custom["heat_mwh"] - base_heat) / (base_heat or 1.0)) * 100.0, 1),
                elec_mwh=res_custom["elec_mwh"],
                elec_diff_pct=round(((res_custom["elec_mwh"] - base_elec) / (base_elec or 1.0)) * 100.0, 1),
                total_cost_rub=res_custom["total_cost_rub"],
                cost_diff_rub=round(res_custom["total_cost_rub"] - base_cost, 0),
                cost_diff_pct=round(((res_custom["total_cost_rub"] - base_cost) / (base_cost or 1.0)) * 100.0, 1),
                violations=res_custom["violations"],
                status_badge="Кастомный" if not res_custom["violations"] else "Есть риски"
            )

        # Формирование временных рядов
        series_points: List[SimulationSeriesPoint] = []
        for i, w in enumerate(weather):
            timestamp = start_time + pd.Timedelta(hours=i+1)
            series_points.append(SimulationSeriesPoint(
                time=timestamp.strftime("%H:%M"),
                baseline_power_kw=res_baseline["power_series"][i],
                custom_power_kw=res_custom["power_series"][i] if res_custom else None,
                aggressive_power_kw=res_aggressive["power_series"][i],
                timestamp=timestamp.isoformat(),
                baseline_temp=res_baseline["temps"][i],
                eco_temp=res_eco["temps"][i],
                aggressive_temp=res_aggressive["temps"][i],
                custom_temp=res_custom["temps"][i] if res_custom else None,
                # Реальные измерения не подключены. Не подменяем факт искусственным рядом.
                fact_temp=None,
                
                baseline_humidity=res_baseline["humidities"][i],
                eco_humidity=res_eco["humidities"][i],
                aggressive_humidity=res_aggressive["humidities"][i],
                custom_humidity=res_custom["humidities"][i] if res_custom else None,
                
                baseline_co2=res_baseline["co2s"][i],
                eco_co2=res_eco["co2s"][i],
                aggressive_co2=res_aggressive["co2s"][i],
                custom_co2=res_custom["co2s"][i] if res_custom else None
            ))

        result = SimulationResult(
            is_demo=True,
            demo_disclaimer="DEMO: Упрощённые эвристические расчёты для демонстрации интерфейса. Модель не калибрована и не проверена на объекте. Прямое управление отключено.",
            model_version=self.version,
            horizon_hours=request.horizon_hours,
            series=series_points,
            baseline_kpi=baseline_kpi,
            eco_kpi=eco_kpi,
            aggressive_kpi=aggressive_kpi,
            custom_kpi=custom_kpi
        )

        if "co2" not in initial_state.available_metrics:
            result.model_assumptions.append("В журнале нет CO₂: для всех вариантов принято начальное значение 800 ppm. Это допущение, а не измерение.")
        return result
