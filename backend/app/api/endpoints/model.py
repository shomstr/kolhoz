from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.dataset_service import dataset_service
from app.services.crop_model_service import crop_model_service
from app.db.store import store

router = APIRouter(prefix='/model', tags=['model'])
class CalibrationRequest(BaseModel):
    start: str | None = None
    end: str | None = None

class CropPredictRequest(BaseModel):
    crop: str

@router.get('/status')
def model_status():
    return {**dataset_service.info(), 'calibration': store.get('calibration'), 'versions': store.get('model_versions', [])}

@router.post('/calibrate')
def calibrate(request: CalibrationRequest):
    try:
        return dataset_service.calibrate(request.start, request.end)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@router.get('/forecast-fact')
def forecast_fact(experiment_id: str):
    import pandas as pd
    import numpy as np
    experiment = next((x for x in store.get('experiment_history', []) if x['id'] == experiment_id), None)
    if not experiment:
        raise HTTPException(404, 'Эксперимент не найден.')
    readings = store.get('measurements', [])
    points = []
    for point in experiment['series']:
        if not point.get('timestamp'):
            continue
        target = pd.Timestamp(point['timestamp'])
        if target.tzinfo is None:
            target = target.tz_localize('Europe/Moscow')
        nearest = min(readings, key=lambda row: abs((pd.Timestamp(row['timestamp'])-target).total_seconds()), default=None)
        actual = nearest['temperature'] if nearest and abs((pd.Timestamp(nearest['timestamp'])-target).total_seconds()) <= 1800 else None
        points.append({'time': target.strftime('%H:%M'), 'fact': actual, 'forecast': point.get('custom_temp') or point['baseline_temp']})
    errors = [abs(p['fact']-p['forecast']) for p in points if p['fact'] is not None]
    return {'points': points, 'matched_points':len(errors), 'mae':round(float(np.mean(errors)),3) if errors else None}

@router.post('/versions/{version}/activate')
def activate_version(version: str):
    record = next((x for x in store.get('model_versions', []) if x['version'] == version), None)
    if not record:
        raise HTTPException(404, 'Версия не найдена.')
    if record.get('dataset_id') != dataset_service.info()['dataset_id']:
        raise HTTPException(422, 'Эта версия получена на другом журнале. Калибруйте текущий набор данных.')
    store.set('calibration', record)
    return record


@router.get('/crops')
def get_crops_model():
    try:
        return crop_model_service.get_info()
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get('/crops/predict')
def predict_crop_climate_get(crop: str):
    try:
        return crop_model_service.predict(crop)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@router.post('/crops/predict')
def predict_crop_climate_post(request: CropPredictRequest):
    try:
        return crop_model_service.predict(request.crop)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
