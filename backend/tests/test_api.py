import csv
import io
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.store import store
import importlib

client = TestClient(app)

@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    module = importlib.import_module('app.db.store')
    monkeypatch.setattr(module, 'DB_PATH', tmp_path / 'state.sqlite')
    store.__init__()


def upload(rows=36, filename='measurements.csv', missing=False, delimiter=','):
    output=io.StringIO()
    writer=csv.writer(output,delimiter=delimiter)
    writer.writerow(['timestamp','temp_air','humidity','co2','ppfd','heating_valve','outdoor_temp'])
    for i in range(rows):
        writer.writerow([(datetime(2026,10,10,9)+timedelta(minutes=i*10)).isoformat(), '' if missing and i==3 else 22+i*.02, 67+i*.03, 810,320,40,6])
    return client.post('/api/data/upload',files={'file':(filename,output.getvalue().encode(),'text/csv')})


def test_health_and_sample_source_are_explicit():
    health=client.get('/api/health').json()
    assert health['real_hardware_control']=='DISABLED'
    current=client.get('/api/climate/current').json()
    assert current['source_kind']=='sample'
    assert 0<=current['humidity']<=100
    assert 'light' in current['available_metrics']
    assert len(client.get('/api/climate/zones').json())==1


def test_import_updates_current_and_history_across_services():
    report=upload().json()
    assert report['applied'] and report['valid_rows']==36
    state=client.get('/api/climate/current').json()
    assert state['source_kind']=='uploaded' and state['temperature']==pytest.approx(22.7)
    assert state['light']==320
    history=client.get('/api/climate/history-24h').json()
    assert len(history)==36 and history[-1]['fact_temp']==state['temperature']
    assert state['last_updated'].endswith('+00:00')
    assert history[0]['time']=='09:00'


def test_gaps_are_preserved_without_interpolation():
    assert upload(missing=True).status_code==200
    history=client.get('/api/climate/history-24h').json()
    assert history[3]['is_gap'] and history[3]['fact_temp'] is None


def test_csv_semicolon_and_invalid_files():
    assert upload(delimiter=';').status_code==200
    assert client.post('/api/data/upload',files={'file':('bad.xlsx',b'bad')}).status_code==422
    assert client.post('/api/data/upload',files={'file':('empty.csv',b'')}).status_code==422


def test_manual_mapping_applies_nonstandard_columns():
    body=b'date_custom,sensor_x,sensor_y\n2026-10-10T10:00,23,65\n2026-10-10T10:10,24,66\n'
    response=client.post('/api/data/upload',files={'file':('custom.csv',body)})
    assert not response.json()['applied']
    mapping={'timestamp_col':'date_custom','temp_air_col':'sensor_x','humidity_col':'sensor_y','co2_col':None,'light_col':None,'heating_valve_col':None}
    assert client.post('/api/data/mapping',json=mapping).status_code==200
    assert client.get('/api/climate/current').json()['temperature']==24
    assert 'co2' not in client.get('/api/climate/current').json()['available_metrics']


def test_simulation_context_reproducibility_and_history():
    upload()
    payload={'horizon_hours':12,'custom_scenario':{'name':'A','heating_temp':21,'vent_min_open':15}}
    first=client.post('/api/experiments/simulate',json=payload).json()
    second=client.post('/api/experiments/simulate',json=payload).json()
    assert first['id']!=second['id']
    assert first['series']==second['series'] and len(first['series'])==12
    assert first['initial_state']['temperature']==pytest.approx(22.7)
    assert first['is_demo'] and first['source_name']=='measurements.csv'
    assert len(client.get('/api/experiments/history').json())==2
    assert client.post('/api/experiments/simulate',json={'horizon_hours':30}).status_code==422


def test_preview_does_not_create_experiment():
    assert client.post('/api/experiments/preview',json={'horizon_hours':24}).status_code==200
    assert client.get('/api/experiments/history').json()==[]


def test_scenario_save_replace_delete():
    client.post('/api/experiments/scenarios',json={'name':'Night'})
    client.post('/api/experiments/scenarios',json={'name':'night','heating_temp':20})
    saved=client.get('/api/experiments/scenarios').json()
    assert len(saved)==1 and saved[0]['heating_temp']==20
    assert client.delete('/api/experiments/scenarios/night').status_code==200
    assert client.get('/api/experiments/scenarios').json()==[]


def test_tariffs_are_used_by_simulation_and_period_projection():
    initial=client.post('/api/experiments/preview',json={'horizon_hours':24}).json()
    tariffs=client.get('/api/economics/tariffs').json()
    tariffs['heat_rate_rub_mwh']*=2
    client.post('/api/economics/tariffs',json=tariffs)
    updated=client.post('/api/experiments/preview',json={'horizon_hours':24}).json()
    assert updated['baseline_kpi']['total_cost_rub']>initial['baseline_kpi']['total_cost_rub']
    month=client.get('/api/economics/summary?period=month').json()
    quarter=client.get('/api/economics/summary?period=quarter').json()
    assert quarter['baseline_monthly_cost_rub']==pytest.approx(month['baseline_monthly_cost_rub']*3,abs=2)
    assert month['historical_confirmed_savings_rub']==0
    tariffs['heat_rate_rub_mwh']=-1
    assert client.post('/api/economics/tariffs',json=tariffs).status_code==422


def test_settings_affect_limits_passport_and_snapshot():
    settings=client.get('/api/settings/').json()
    settings.update(greenhouse_name='Объект тест',area_ha=2,humidity_max_critical=50)
    assert client.post('/api/settings/',json=settings).status_code==200
    assert client.get('/api/climate/current').json()['greenhouse_name']=='Объект тест'
    assert client.get('/api/data/passport').json()['area_ha']==2
    result=client.post('/api/experiments/preview',json={'horizon_hours':24}).json()
    assert 'Влажность выше допустимого максимума' in result['baseline_kpi']['violations']
    settings['temp_min_critical']=40
    assert client.post('/api/settings/',json=settings).status_code==422


def test_calibration_temporal_holdout_and_version_activation():
    upload()
    first=client.post('/api/model/calibrate',json={}).json()
    assert first['train_rows']==28 and first['test_rows']==8
    assert len(first['predictions'])==8
    assert first['metrics']['temperature']['mae']==pytest.approx(0,abs=.001)
    second=client.post('/api/model/calibrate',json={}).json()
    assert second['version']!=first['version']
    assert client.post('/api/model/versions/'+first['version']+'/activate').status_code==200
    assert client.get('/api/model/status').json()['calibration']['version']==first['version']
    assert client.post('/api/model/calibrate',json={'start':'2030-01-01'}).status_code==422


def test_decision_journal_and_archive():
    result=client.post('/api/experiments/simulate',json={'horizon_hours':6}).json()
    response=client.post('/api/reports/decisions',json={'experiment_id':result['id'],'scenario_name':'Выбранный','parameters_summary':'T=22','expected_effect':'Расчёт','notes':'Причина'})
    decision=response.json()
    assert response.status_code==200 and decision['experiment_id']==result['id']
    assert client.patch('/api/reports/decisions/'+decision['id']+'/archive').json()['status']=='Архив'
    assert client.get('/api/reports/decisions?status=Принято').json()==[]


def test_post_decision_forecast_fact_matches_uploaded_observations():
    upload()
    experiment=client.post('/api/experiments/simulate',json={'horizon_hours':6}).json()
    output=io.StringIO();writer=csv.writer(output);writer.writerow(['timestamp','temp_air','humidity'])
    for point in experiment['series']:writer.writerow([point['timestamp'],point['baseline_temp']+1,65])
    assert client.post('/api/data/upload',files={'file':('later.csv',output.getvalue().encode())}).status_code==200
    comparison=client.get('/api/model/forecast-fact',params={'experiment_id':experiment['id']}).json()
    assert comparison['matched_points']==6 and comparison['mae']==1


def test_temporal_gaps_and_invalid_timezone_are_visible():
    body=b'timestamp,temp_air,humidity\n2026-10-10T10:00,22,65\n2026-10-10T10:10,22,65\n2026-10-10T11:10,22,65\n2026-10-10T11:20,22,65\n'
    report=client.post('/api/data/upload',files={'file':('gap.csv',body)}).json()
    assert report['quality_status']=='WARNING'
    assert any(point['is_gap'] for point in client.get('/api/climate/history-24h').json())
    cfg=client.get('/api/settings/').json();cfg['timezone']='Invalid/Zone'
    assert client.post('/api/settings/',json=cfg).status_code==422


def test_calibration_cannot_be_reused_on_changed_dataset_with_same_name():
    upload(rows=36)
    version=client.post('/api/model/calibrate',json={}).json()['version']
    upload(rows=40)
    assert client.post('/api/model/versions/'+version+'/activate').status_code==422


def test_calibration_date_filter_uses_local_timezone():
    out=io.StringIO();w=csv.writer(out);w.writerow(['timestamp','temp_air','humidity'])
    for i in range(36):w.writerow([(datetime(2026,10,10,1)+timedelta(minutes=i*10)).isoformat(),22+i*.02,67])
    assert client.post('/api/data/upload',files={'file':('early.csv',out.getvalue().encode())}).status_code==200
    calibration=client.post('/api/model/calibrate',json={'start':'2026-10-10','end':'2026-10-10'})
    assert calibration.status_code==200 and calibration.json()['train_rows']==28
    assert calibration.json()['predictions'][0]['time']=='05:40'


def test_nonfinite_csv_values_remain_visible_as_gaps():
    body=b'timestamp,temp_air,humidity\n2026-10-10T10:00,22,65\n2026-10-10T10:10,inf,65\n'
    response=client.post('/api/data/upload',files={'file':('invalid-numbers.csv',body)})
    assert response.status_code==200 and response.json()['missing_rate_pct']>0
    assert client.get('/api/climate/history-24h').json()[-1]['fact_temp'] is None


def test_column_inference_does_not_confuse_outdoor_and_inside_temperature():
    raw=b'timestamp,outside_temperature,indoor_temperature,humidity\n2026-10-10T12:00,6,24,67\n'
    report=client.post('/api/data/upload',files={'file':('inside-outside.csv',raw)}).json()
    assert report['column_mapping']['temp_air_col']=='indoor_temperature'
    assert client.get('/api/climate/current').json()['temperature']==24


def test_crop_model_endpoints():
    info = client.get('/api/model/crops').json()
    assert info['status'] == 'ready'
    assert info['dataset_rows'] == 500
    assert set(info['available_crops']) == {'Кабачки', 'Огурцы', 'Помидоры'}
    assert 'temperature_mae' in info['metrics']

    # Test GET prediction with exact name
    res_cuc = client.get('/api/model/crops/predict?crop=Огурцы')
    assert res_cuc.status_code == 200
    data_cuc = res_cuc.json()
    assert data_cuc['crop'] == 'Огурцы'
    assert 80 <= data_cuc['humidity'] <= 90
    assert 24 <= data_cuc['temperature'] <= 27
    assert data_cuc['light_lux'] > 5000
    assert data_cuc['light_umol'] > 0

    # Test GET prediction with alias 'томат'
    res_tom = client.get('/api/model/crops/predict?crop=томат')
    assert res_tom.status_code == 200
    assert res_tom.json()['crop'] == 'Помидоры'

    # Test POST prediction
    res_post = client.post('/api/model/crops/predict', json={'crop': 'Кабачки'})
    assert res_post.status_code == 200
    assert res_post.json()['crop'] == 'Кабачки'
    assert 'recommended_scenario' in res_post.json()

    # Test unknown crop
    res_unknown = client.get('/api/model/crops/predict?crop=Банан')
    assert res_unknown.status_code == 422
