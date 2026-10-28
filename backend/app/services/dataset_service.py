"""Persisted CSV observations, temporal forecast validation and model versions."""
import io
import math
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from app.core.config import SAMPLE_CSV_PATH
from app.db.store import store
from app.models.schemas import ClimateCurrent, ClimateHistoryPoint, ColumnMapping, GreenhousePassport


def finite(value, default=None):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


class DatasetService:
    def stage(self, content: bytes, filename: str, source_kind='uploaded'):
        frame = pd.read_csv(io.BytesIO(content), sep=None, engine='python', encoding='utf-8-sig').replace([np.inf,-np.inf],np.nan)
        rows = frame.astype(object).where(pd.notna(frame), None).to_dict('records')
        store.set('pending_dataset', {'filename': filename, 'rows': rows, 'source_kind': source_kind})

    def activate(self, mapping: ColumnMapping):
        pending = store.get('pending_dataset')
        if not pending:
            raise ValueError('Сначала загрузите CSV-файл.')
        frame = pd.DataFrame(pending['rows'])
        required = [mapping.timestamp_col, mapping.temp_air_col, mapping.humidity_col]
        if len(set(required)) != 3 or any(col not in frame.columns for col in required):
            raise ValueError('Укажите разные столбцы времени, температуры и влажности.')
        timestamps = pd.to_datetime(frame[mapping.timestamp_col], errors='coerce')
        if timestamps.dt.tz is None:
            timestamps = timestamps.dt.tz_localize(store.get('settings', {}).get('timezone', 'Europe/Moscow').split(' ')[0], ambiguous='NaT', nonexistent='NaT')
        timestamps = timestamps.dt.tz_convert('UTC')
        rows = []
        for i, raw in frame.iterrows():
            if pd.isna(timestamps.iloc[i]):
                continue
            point = {'timestamp': timestamps.iloc[i].isoformat()}
            for target, col in [('temperature', mapping.temp_air_col), ('humidity', mapping.humidity_col), ('co2', mapping.co2_col), ('heating', mapping.heating_valve_col), ('solar', mapping.solar_col), ('outdoor_temp', mapping.outdoor_temp_col), ('light', mapping.light_col), ('vent', mapping.vent_open_col), ('screens', mapping.screens_col), ('lamps', mapping.lamps_col)]:
                point[target] = finite(raw.get(col)) if col else None
            if point['temperature'] is not None and not -10 <= point['temperature'] <= 50:
                point['temperature'] = None
            if point['humidity'] is not None and not 0 <= point['humidity'] <= 100:
                point['humidity'] = None
            rows.append(point)
        rows = sorted({row['timestamp']: row for row in rows}.values(), key=lambda r: r['timestamp'])
        if not any(row['temperature'] is not None and row['humidity'] is not None for row in rows):
            raise ValueError('Не найдено ни одной пригодной строки с временем, температурой и влажностью.')
        store.set('measurements', rows)
        store.set('calibration', None)
        store.set('dataset_meta', {'filename': pending['filename'], 'source_kind': pending.get('source_kind', 'uploaded'), 'dataset_id': hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(), 'imported_at': datetime.now(ZoneInfo('Europe/Moscow')).isoformat()})
        store.set('column_mapping', mapping.model_dump())
        return len(rows)

    def observations(self):
        rows = store.get('measurements')
        if rows:
            return rows
        frame = pd.read_csv(SAMPLE_CSV_PATH)
        return [{'timestamp': pd.Timestamp(r['timestamp'], tz='Europe/Moscow').isoformat(), 'temperature': finite(r.get('temp_air')), 'humidity': finite(r.get('humidity')), 'co2': finite(r.get('co2')), 'heating': finite(r.get('heating_valve')), 'solar': finite(r.get('solar_radiation')), 'outdoor_temp': finite(r.get('outdoor_temp')), 'light': finite(r.get('ppfd')), 'vent': finite(r.get('vent_open')), 'screens': finite(r.get('screen_pct')), 'lamps': finite(r.get('lighting_pct'))} for r in frame.to_dict('records')]

    def info(self):
        rows = self.observations()
        meta = store.get('dataset_meta', {'filename': 'sample_greenhouse_log.csv', 'source_kind': 'sample'})
        return {**meta, 'dataset_id': hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(), 'total_rows': len(rows), 'start': rows[0]['timestamp'] if rows else None, 'end': rows[-1]['timestamp'] if rows else None, 'model_name': 'Баланс тепла и базовый прогноз', 'model_status': 'Расчётный алгоритм без полевой проверки', 'hardware_control': False, 'timezone':store.get('settings',{}).get('timezone','Europe/Moscow').split(' ')[0]}

    def current_climate(self) -> Optional[ClimateCurrent]:
        rows = self.observations()
        passport = GreenhousePassport.model_validate(store.get('passport', {}))
        cfg = store.get('settings', {})
        meta = store.get('dataset_meta', {'source_kind':'sample','filename':'sample_greenhouse_log.csv'})
        def latest(key, default):
            return next((r[key] for r in reversed(rows) if r.get(key) is not None), default)
        return ClimateCurrent(temperature=latest('temperature', 21.8), humidity=latest('humidity', 67), co2=latest('co2', 0), light=latest('light', 0), outdoor_temp=latest('outdoor_temp', 0), outdoor_solar=latest('solar',0), available_metrics=[key for key in ['temperature','humidity','co2','light'] if any(r.get(key) is not None for r in rows)], source_kind=meta['source_kind'], source_name=meta['filename'], status='IMPORTED', timezone=cfg.get('timezone','Europe/Moscow').split(' ')[0], status_text='По данным журнала', last_updated=rows[-1]['timestamp'], greenhouse_name=cfg.get('greenhouse_name', passport.name), zone_name=cfg.get('zone_name', passport.zone), crop=cfg.get('crop', passport.crop), area_ha=cfg.get('area_ha', passport.area_ha))

    def history(self, hours=24) -> Optional[list[ClimateHistoryPoint]]:
        all_rows = self.observations()
        cutoff = pd.Timestamp(all_rows[-1]['timestamp']) - pd.Timedelta(hours=hours)
        rows = [r for r in all_rows if pd.Timestamp(r['timestamp']) >= cutoff]
        original_times = pd.to_datetime([r['timestamp'] for r in rows], utc=True)
        intervals = pd.Series(original_times).diff().dt.total_seconds().dropna()
        positive = intervals[intervals > 0]
        regular_step = float(positive.median()) if not positive.empty else 600
        gaps = {rows[i]['timestamp']: (pd.Timestamp(rows[i-1]['timestamp']) + pd.Timedelta(seconds=regular_step)).isoformat() for i in range(1,len(rows)) if (pd.Timestamp(rows[i]['timestamp'])-pd.Timestamp(rows[i-1]['timestamp'])).total_seconds() > regular_step*1.5}
        step = max(1, len(rows) // 300)
        indices = set(range(0,len(rows),step)) | {len(rows)-1}
        indices.update(i for i,row in enumerate(rows) if row['timestamp'] in gaps or row['temperature'] is None or row['humidity'] is None)
        rows = [rows[i] for i in sorted(indices) if i >= 0]
        result = []
        previous = None
        drift = (store.get('calibration', {}) or {}).get('drift', {})
        for row in rows:
            if row['timestamp'] in gaps:
                missing_time = pd.Timestamp(gaps[row['timestamp']])
                result.append(ClimateHistoryPoint(timestamp=missing_time.isoformat(),time=missing_time.tz_convert(store.get('settings',{}).get('timezone','Europe/Moscow').split(' ')[0]).strftime('%H:%M'),is_gap=True))
            stamp = pd.Timestamp(row['timestamp'])
            kwargs = dict(timestamp=row['timestamp'], time=stamp.tz_convert(store.get('settings', {}).get('timezone', 'Europe/Moscow').split(' ')[0]).strftime('%H:%M'), fact_temp=row['temperature'], fact_humidity=row['humidity'], fact_co2=row['co2'], fact_light=row.get('light'), outdoor_temp=row['outdoor_temp'], outdoor_solar=row['solar'], heating_valve_pct=row['heating'], vent_open_pct=row.get('vent'), screens_pct=row.get('screens'), lamps_pct=row.get('lamps'), is_gap=row['temperature'] is None or row['humidity'] is None)
            for source, target in [('temperature', 'forecast_temp'), ('humidity', 'forecast_humidity'), ('co2', 'forecast_co2')]:
                kwargs[target] = round(previous[source] + drift.get(source, 0), 2) if previous and previous.get(source) is not None else None
            result.append(ClimateHistoryPoint(**kwargs))
            previous = row
        return result

    def calibrate(self, start=None, end=None):
        rows = self.observations()
        metadata = self.info()
        if start:
            rows = [r for r in rows if pd.Timestamp(r['timestamp']).tz_convert(metadata['timezone']).date() >= pd.Timestamp(start).date()]
        if end:
            rows = [r for r in rows if pd.Timestamp(r['timestamp']).tz_convert(metadata['timezone']).date() <= pd.Timestamp(end).date()]
        if len(rows) < 12:
            raise ValueError('Для временного разделения обучения и теста нужно не менее 12 строк.')
        split = int(len(rows) * .8)
        metrics, drift, predictions = {}, {}, []
        for field in ['temperature', 'humidity', 'co2']:
            train = [r[field] for r in rows[:split] if r.get(field) is not None]
            drift[field] = round(float(np.median(np.diff(train))), 5) if len(train) > 1 else 0
            errors, baseline_errors = [], []
            for index in range(split, len(rows)):
                prior, actual = rows[index-1].get(field), rows[index].get(field)
                if prior is None or actual is None:
                    continue
                predicted = prior + drift[field]
                errors.append(abs(predicted-actual))
                baseline_errors.append(abs(prior-actual))
                if field == 'temperature':
                    predictions.append({'time': pd.Timestamp(rows[index]['timestamp']).tz_convert(metadata['timezone']).strftime('%H:%M'), 'fact': actual, 'forecast': round(predicted, 3)})
            metrics[field] = {'mae': round(float(np.mean(errors)), 3) if errors else None, 'baseline_mae': round(float(np.mean(baseline_errors)), 3) if baseline_errors else None, 'test_points': len(errors)}
        versions = store.get('model_versions', [])
        record = {'version': f'forecast-{len(versions)+1}', 'created_at': datetime.now(ZoneInfo('Europe/Moscow')).isoformat(), 'dataset': metadata['filename'], 'source_kind': metadata['source_kind'], 'dataset_id': metadata['dataset_id'], 'train_rows': split, 'test_rows': len(rows)-split, 'start': rows[0]['timestamp'], 'end': rows[-1]['timestamp'], 'test_start': rows[split]['timestamp'], 'drift': drift, 'metrics': metrics, 'predictions': predictions, 'method': 'Одношаговый прогноз: предыдущее значение + медианный дрейф. Последние 20% ряда — независимый тест.'}
        store.set('calibration', record)
        store.set('model_versions', [record, *versions])
        return record


dataset_service = DatasetService()
