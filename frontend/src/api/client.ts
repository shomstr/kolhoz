import type { ClimateCurrent, ClimateHistoryPoint, ScenarioEquipmentParams, SimulationRequest, SimulationResult, DataQualityReport, ColumnMapping, GreenhousePassport, TariffConfig, EconomicsSummary, DecisionRecord, AppSettings, ModelStatus, Calibration, ForecastFact, CropModelInfo, CropPredictionResult } from '../types';

function validationMessage(item: {type?:string;msg:string;loc?:string[];ctx?:Record<string,any>}):string {
  const labels:Record<string,string>={area_ha:'Площадь',heating_capacity_mw:'Мощность отопления',lighting_capacity_w_m2:'Мощность досветки',heating_temp:'Температура уставки',vent_min_open:'Вентиляция',lighting_intensity:'Интенсивность досветки',temp_min_critical:'Минимальная температура',temp_max_critical:'Максимальная температура',humidity_max_critical:'Максимальная влажность',name:'Название',timestamp_col:'Столбец времени',temp_air_col:'Столбец температуры',humidity_col:'Столбец влажности',timezone:'Часовой пояс'};
  const name=labels[String(item.loc?.[item.loc.length-1])]||'Значение поля';const context=item.ctx||{};
  if(item.type==='value_error')return item.msg.replace(/^Value error, /,'');
  if(item.type==='greater_than')return `${name}: укажите число больше ${context.gt}.`;
  if(item.type==='greater_than_equal')return `${name}: минимум ${context.ge}.`;
  if(item.type==='less_than_equal')return `${name}: максимум ${context.le}.`;
  if(item.type==='string_too_short'||item.type==='missing')return `${name}: заполните обязательное поле.`;
  if(item.type==='literal_error')return `${name}: выберите один из доступных вариантов.`;
  return `${name}: проверьте формат и допустимый диапазон.`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init).catch(() => { throw new Error('Нет связи с сервером. Проверьте подключение и повторите действие.'); });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(validationMessage).join(' ') : `Не удалось выполнить действие (${response.status}).`);
  }
  return body as T;
}
const post = <T>(path: string, body: unknown) => request<T>(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
export const api = {
  getHealth: () => request<{status: string; is_demo_mode: boolean}>('/health'),
  getCurrentClimate: () => request<ClimateCurrent>('/climate/current'),
  getClimateHistory: () => request<ClimateHistoryPoint[]>('/climate/history-24h'),
  simulate: (body: SimulationRequest) => post<SimulationResult>('/experiments/simulate', body),
  preview: (body: SimulationRequest) => post<SimulationResult>('/experiments/preview', body),
  getPresets: () => request<Record<string,ScenarioEquipmentParams>>('/experiments/presets'),
  getSavedScenarios: () => request<ScenarioEquipmentParams[]>('/experiments/scenarios'),
  saveScenario: (body: ScenarioEquipmentParams) => post<ScenarioEquipmentParams>('/experiments/scenarios', body),
  deleteScenario: (name: string) => request('/experiments/scenarios/'+encodeURIComponent(name), {method:'DELETE'}),
  getExperiments: () => request<SimulationResult[]>('/experiments/history'),
  getDefaultQuality: () => request<DataQualityReport>('/data/quality-default'),
  uploadDataset: (file: File) => { const body = new FormData(); body.append('file',file); return request<DataQualityReport>('/data/upload', {method:'POST',body}); },
  getPassport: () => request<GreenhousePassport>('/data/passport'),
  updatePassport: (body: GreenhousePassport) => post<GreenhousePassport>('/data/passport',body),
  saveColumnMapping: (body: ColumnMapping) => post<ColumnMapping>('/data/mapping',body),
  getEconomics: (period='month') => request<EconomicsSummary>(`/economics/summary?period=${period}`),
  updateTariffs: (body: TariffConfig) => post<TariffConfig>('/economics/tariffs',body),
  getDecisions: () => request<DecisionRecord[]>('/reports/decisions'),
  createDecision: (body: {scenario_name: string; parameters_summary: string; expected_effect: string; notes?: string; experiment_id?: string}) => post<DecisionRecord>('/reports/decisions',body),
  archiveDecision: (id: string) => request<DecisionRecord>(`/reports/decisions/${id}/archive`,{method:'PATCH'}),
  getSettings: () => request<AppSettings>('/settings/'),
  updateSettings: (body: AppSettings) => post<AppSettings>('/settings/',body),
  getModelStatus: () => request<ModelStatus>('/model/status'),
  calibrate: (body: {start?: string; end?: string}) => post<Calibration>('/model/calibrate',body),
  activateCalibration: (version: string) => post<Calibration>(`/model/versions/${encodeURIComponent(version)}/activate`, {}),
  getForecastFact: (id: string) => request<ForecastFact>(`/model/forecast-fact?experiment_id=${encodeURIComponent(id)}`),
  getCropsModelInfo: () => request<CropModelInfo>('/model/crops'),
  predictCropClimate: (crop: string) => request<CropPredictionResult>(`/model/crops/predict?crop=${encodeURIComponent(crop)}`),
};
