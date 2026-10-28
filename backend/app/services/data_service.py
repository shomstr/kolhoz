import io
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from app.models.schemas import (
    ClimateCurrent,
    ClimateHistoryPoint,
    DataQualityReport,
    ColumnMapping,
    GreenhousePassport,
)
from app.core.config import SAMPLE_CSV_PATH
from app.db.store import store

class DataService:
    def __init__(self):
        self._passport = GreenhousePassport.model_validate(store.get("passport", GreenhousePassport().model_dump()))
        self._column_mapping = ColumnMapping.model_validate(store.get("column_mapping", ColumnMapping().model_dump()))
        self._ensure_sample_csv()

    def _ensure_sample_csv(self):
        """Создает демонстрационный эталонный CSV-файл журнала теплицы"""
        if not SAMPLE_CSV_PATH.exists():
            records = []
            base_time = datetime(2026, 10, 9, 0, 0)
            for i in range(144): # 24 часа по 10 минут
                t = base_time + timedelta(minutes=10 * i)
                hour = t.hour + t.minute / 60.0
                solar = max(0.0, 320.0 * math.sin((hour - 8) * math.pi / 9)) if 8 <= hour <= 17 else 0.0
                t_air = 21.0 + 1.2 * math.sin((hour - 7) * math.pi / 12) + (0.5 if solar > 100 else 0.0)
                rh = 68.0 - 5.0 * (solar / 320.0) if solar > 0 else 71.0
                co2 = 800.0 + 50.0 * math.cos(hour * math.pi / 12)
                valve = max(10.0, 50.0 - 15.0 * (t_air - 20.0))

                records.append({
                    "timestamp": t.strftime("%Y-%m-%d %H:%M"),
                    "temp_air": round(t_air, 1),
                    "humidity": round(rh, 1),
                    "co2": int(co2),
                    "heating_valve": round(valve, 1),
                    "solar_radiation": round(solar, 1),
                    "outdoor_temp": round(4.0 + 3.0 * math.sin((hour - 8) * math.pi / 12), 1)
                })
            df = pd.DataFrame(records)
            SAMPLE_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(SAMPLE_CSV_PATH, index=False)

    def get_current_climate(self) -> ClimateCurrent:
        from app.services.dataset_service import dataset_service
        return dataset_service.current_climate()

    def get_climate_history_24h(self) -> List[ClimateHistoryPoint]:
        from app.services.dataset_service import dataset_service
        return dataset_service.history()

    def analyze_uploaded_file(
        self,
        content_bytes: bytes,
        filename: str,
        preferred_mapping: Optional[ColumnMapping] = None,
    ) -> DataQualityReport:
        """Проверяет CSV, не подменяя ошибочный файл демонстрационным набором."""
        if not filename.lower().endswith(".csv"):
            raise ValueError("Поддерживается импорт CSV. Сохраните журнал контроллера в формате .csv.")
        if not content_bytes:
            raise ValueError("Файл пустой.")
        try:
            df = pd.read_csv(io.BytesIO(content_bytes), sep=None, engine="python", encoding="utf-8-sig").replace([np.inf, -np.inf], np.nan)
        except Exception as exc:
            raise ValueError("Не удалось прочитать CSV. Проверьте разделитель, кодировку и строку заголовков.") from exc
        if df.empty or len(df.columns) == 0:
            raise ValueError("В файле нет строк с данными.")

        total_rows = len(df)
        cols = [str(col) for col in df.columns]

        def find_column(tokens: tuple[str, ...], exclude: tuple[str, ...] = ()) -> str:
            for col in cols:
                lowered = col.lower().strip()
                if any(token in lowered for token in tokens) and not any(token in lowered for token in exclude):
                    return col
            return ""

        mapping = ColumnMapping(
            light_col=find_column(("ppfd", "light", "освещ")) or None,
            vent_open_col=find_column(("vent_open", "вент")) or None,
            screens_col=find_column(("screen_pct", "экраны")) or None,
            lamps_col=find_column(("lighting_pct", "лампы")) or None,
            timestamp_col=find_column(("time", "date", "время", "дата")),
            temp_air_col=find_column(("temp", "темп", "t_air"), ("outdoor", "наруж", "outside", "external")),
            humidity_col=find_column(("hum", "влажн", "rh"), ("outdoor", "наруж", "outside", "external")),
            co2_col=find_column(("co2", "co₂")),
            heating_valve_col=find_column(("valve", "отопл", "клапан")),
            solar_col=find_column(("solar", "радиац", "солн")) or None,
            outdoor_temp_col=find_column(("outdoor", "наружн")) or None,
        )
        preferred = preferred_mapping or self._column_mapping
        for field in ("timestamp_col", "temp_air_col", "humidity_col", "co2_col", "heating_valve_col", "solar_col", "outdoor_temp_col", "light_col", "vent_open_col", "screens_col", "lamps_col"):
            preferred_column = getattr(preferred, field)
            if preferred_column in cols:
                setattr(mapping, field, preferred_column)

        cell_count = max(1, total_rows * len(cols))
        missing_rate = round(float(df.isna().sum().sum()) / cell_count * 100, 2)
        timestamp_errors = 0
        temporal_gaps = 0
        duplicate_times = 0
        sample_interval = 0
        if mapping.timestamp_col:
            parsed = pd.to_datetime(df[mapping.timestamp_col], errors="coerce")
            timestamp_errors = int(parsed.isna().sum())
            duplicate_times = int(parsed.dropna().duplicated().sum())
            intervals = parsed.dropna().sort_values().diff().dt.total_seconds().div(60).dropna()
            if not intervals.empty:
                positive_intervals = intervals[intervals > 0]
                sample_interval = max(1, int(round(float(positive_intervals.median())))) if not positive_intervals.empty else 0
                temporal_gaps = int((intervals > sample_interval * 1.5).sum()) if sample_interval else 0

        outliers_count = 0
        invalid_cells = timestamp_errors
        unit_range_errors = 0
        checked_unit_cells = 0
        if mapping.temp_air_col:
            raw_temperature = df[mapping.temp_air_col]
            temperature = pd.to_numeric(raw_temperature, errors="coerce")
            invalid_cells += int(temperature.isna().sum())
            unit_range_errors += int((raw_temperature.notna() & temperature.isna()).sum())
            checked_unit_cells += total_rows
            temp_outliers = int(((temperature < -10) | (temperature > 50)).sum())
            outliers_count += temp_outliers
            unit_range_errors += temp_outliers
        if mapping.humidity_col:
            raw_humidity = df[mapping.humidity_col]
            humidity = pd.to_numeric(raw_humidity, errors="coerce")
            invalid_cells += int(humidity.isna().sum())
            unit_range_errors += int((raw_humidity.notna() & humidity.isna()).sum())
            checked_unit_cells += total_rows
            humidity_outliers = int(((humidity < 0) | (humidity > 100)).sum())
            outliers_count += humidity_outliers
            unit_range_errors += humidity_outliers
        unit_errors = round(unit_range_errors / max(1, checked_unit_cells) * 100, 1)
        outliers_pct = round(outliers_count / max(1, checked_unit_cells) * 100, 1)

        required_missing = [
            label for label, column in (("время", mapping.timestamp_col), ("температура", mapping.temp_air_col), ("влажность", mapping.humidity_col))
            if not column
        ]
        invalid_values_pct = invalid_cells / max(1, total_rows * 3) * 100
        if missing_rate >= 5 or unit_errors >= 3 or outliers_pct >= 5 or invalid_values_pct >= 3 or temporal_gaps or duplicate_times or required_missing:
            quality_status = "WARNING"
        elif missing_rate > 0 or outliers_pct > 0 or invalid_cells > 0:
            quality_status = "ACCEPTABLE"
        else:
            quality_status = "EXCELLENT"

        preview = df.head(5).astype(object).where(pd.notna(df), None).to_dict(orient="records")
        messages = []
        if required_missing:
            messages.append(f"Не найдены обязательные столбцы: {', '.join(required_missing)}. Сопоставьте их вручную.")
        else:
            messages.append("Столбцы времени, температуры и влажности распознаны; проверьте сопоставление перед использованием.")
        messages.append(f"Некорректных/пустых значений времени, температуры и влажности: {invalid_cells}.")
        messages.append(f"Возможных ошибок единиц или выхода за диапазон температуры/влажности: {unit_range_errors}. Автоматического пересчёта единиц нет.")
        messages.append(f"Медианный шаг временного ряда: {sample_interval} мин." if sample_interval else "Шаг временного ряда определить не удалось.")
        messages.append(f"Значений вне проверяемых диапазонов: {outliers_count}.")
        messages.append(f"Разрывов регулярного временного ряда: {temporal_gaps}; повторяющихся отметок времени: {duplicate_times}.")

        return DataQualityReport(
            filename=filename,
            total_rows=total_rows,
            missing_rate_pct=missing_rate,
            unit_errors_pct=unit_errors,
            sample_interval_min=sample_interval,
            outliers_pct=outliers_pct,
            quality_status=quality_status,
            detected_columns=cols,
            column_mapping=mapping,
            preview_rows=preview,
            validation_messages=messages,
        )

    def get_passport(self) -> GreenhousePassport:
        return GreenhousePassport.model_validate(store.get("passport", self._passport.model_dump()))

    def update_passport(self, new_passport: GreenhousePassport) -> GreenhousePassport:
        self._passport = new_passport
        store.set("passport", new_passport.model_dump())
        cfg = store.get("settings", {})
        cfg.update(greenhouse_name=new_passport.name, zone_name=new_passport.zone, crop=new_passport.crop, area_ha=new_passport.area_ha)
        store.set("settings", cfg)
        return self._passport

    def get_column_mapping(self) -> ColumnMapping:
        return ColumnMapping.model_validate(store.get("column_mapping", self._column_mapping.model_dump()))

    def update_column_mapping(self, mapping: ColumnMapping) -> ColumnMapping:
        self._column_mapping = mapping
        store.set("column_mapping", mapping.model_dump())
        return self._column_mapping
