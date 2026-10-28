export type NavigationPage =
  | 'overview'
  | 'climate'
  | 'experiments'
  | 'data'
  | 'economics'
  | 'reports'
  | 'settings';

export interface ClimateTargetRanges {
  temp_min: number;
  temp_max: number;
  humidity_min: number;
  humidity_max: number;
  co2_min: number;
  co2_max: number;
  light_min: number;
  light_max: number;
}

export interface ClimateCurrent {
  available_metrics?: string[];
  source_kind: string;
  source_name: string;
  timezone?: string;
  temperature: number;
  humidity: number;
  co2: number;
  light: number;
  outdoor_temp: number;
  outdoor_humidity: number;
  outdoor_solar: number;
  targets: ClimateTargetRanges;
  status: string;
  status_text: string;
  last_updated: string;
  greenhouse_name: string;
  zone_id: string;
  zone_name: string;
  crop: string;
  area_ha: number;
  cycle: string;
}

export interface ClimateHistoryPoint {
  timestamp?: string;
  time: string;
  fact_temp?: number | null;
  forecast_temp?: number | null;
  target_temp_min: number;
  target_temp_max: number;
  
  fact_humidity?: number | null;
  forecast_humidity?: number | null;
  target_humidity_min: number;
  target_humidity_max: number;
  
  fact_co2?: number | null;
  forecast_co2?: number | null;
  target_co2_min: number;
  target_co2_max: number;
  
  fact_light?: number | null;
  forecast_light?: number | null;
  target_light_min: number;
  target_light_max: number;
  
  outdoor_temp: number;
  outdoor_humidity?: number;
  outdoor_solar?: number;
  heating_valve_pct: number;
  vent_open_pct: number;
  screens_pct: number;
  lamps_pct: number;
  is_gap?: boolean;
}

export interface ZoneInfo {
  id: string;
  name: string;
  crop: string;
  area: string;
  status: string;
  temp: number;
  humidity: number;
  co2: number;
  light: number;
}

export interface ScenarioEquipmentParams {
  name: string;
  heating_temp: number;
  vent_min_open: number;
  screen_mode: string;
  lighting_intensity: number;
  co2_target: number;
  night_temp_drop: number;
}

export interface SimulationRequest {
  horizon_hours: number;
  custom_scenario?: ScenarioEquipmentParams | null;
  preset_baseline?: ScenarioEquipmentParams | null;
  preset_eco?: ScenarioEquipmentParams | null;
  preset_aggressive?: ScenarioEquipmentParams | null;
}

export interface SimulationSeriesPoint {
  baseline_power_kw?: number|null;
  custom_power_kw?: number|null;
  aggressive_power_kw?: number|null;
  timestamp?: string;
  time: string;
  baseline_temp: number;
  eco_temp: number;
  aggressive_temp: number;
  custom_temp?: number | null;
  fact_temp?: number | null;
  
  baseline_humidity: number;
  eco_humidity: number;
  aggressive_humidity: number;
  custom_humidity?: number | null;
  
  baseline_co2: number;
  eco_co2: number;
  aggressive_co2: number;
  custom_co2?: number | null;
}

export interface ScenarioKpi {
  scenario_name: string;
  heat_mwh: number;
  heat_diff_pct: number;
  elec_mwh: number;
  elec_diff_pct: number;
  total_cost_rub: number;
  cost_diff_rub: number;
  cost_diff_pct: number;
  violations: string[];
  status_badge: string;
}

export interface SimulationResult {
  request?: SimulationRequest;
  id?: string;
  created_at?: string;
  initial_state?: ClimateCurrent;
  parameters?: ScenarioEquipmentParams;
  source_name: string;
  is_demo: boolean;
  demo_disclaimer: string;
  model_version: string;
  horizon_hours: number;
  series: SimulationSeriesPoint[];
  baseline_kpi: ScenarioKpi;
  eco_kpi: ScenarioKpi;
  aggressive_kpi: ScenarioKpi;
  custom_kpi?: ScenarioKpi | null;
  model_assumptions: string[];
}

export interface ColumnMapping {
  light_col?: string|null;
  vent_open_col?: string|null;
  screens_col?: string|null;
  lamps_col?: string|null;
  timestamp_col: string;
  temp_air_col: string;
  humidity_col: string;
  co2_col?: string|null;
  heating_valve_col?: string|null;
  solar_col?: string|null;
  outdoor_temp_col?: string|null;
}

export interface DataQualityReport {
  applied: boolean;
  valid_rows: number;
  filename: string;
  total_rows: number;
  missing_rate_pct: number;
  unit_errors_pct: number;
  sample_interval_min: number;
  outliers_pct: number;
  quality_status: string;
  detected_columns: string[];
  column_mapping: ColumnMapping;
  preview_rows: Record<string, any>[];
  validation_messages: string[];
}

export interface GreenhousePassport {
  name: string;
  zone: string;
  crop: string;
  area_ha: number;
  glass_type: string;
  screen_type: string;
  heating_capacity_mw: number;
  lighting_capacity_w_m2: number;
  ventilation_type: string;
  co2_system: string;
  sowing_date: string;
  planned_yield_kg_m2: number;
}

export interface TariffConfig {
  implementation_cost_rub: number;
  heat_rate_rub_mwh: number;
  elec_day_rate_rub_mwh: number;
  elec_night_rate_rub_mwh: number;
  co2_rate_rub_kg: number;
}

export interface CostStructureItem {
  category: string;
  heating: number;
  lighting: number;
  ventilation: number;
  other: number;
}

export interface ResourceBreakdownItem {
  resource: string;
  unit: string;
  current: number;
  eco_val: number;
  eco_diff: string;
  baseline_val: number;
  baseline_diff: string;
  aggressive_val: number;
  aggressive_diff: string;
}

export interface EconomicsSummary {
  period: string;
  tariffs: TariffConfig;
  eco_savings_pct_heat: number;
  eco_savings_pct_elec: number;
  eco_monthly_savings_rub: number;
  baseline_monthly_cost_rub: number;
  eco_monthly_cost_rub: number;
  aggressive_monthly_cost_rub: number;
  payback_months_min: number | null;
  payback_months_max: number | null;
  expected_economy_min_rub: number;
  expected_economy_max_rub: number;
  cost_structure: CostStructureItem[];
  resource_breakdown: ResourceBreakdownItem[];
  historical_confirmed_savings_rub: number;
  modeled_projected_savings_rub: number;
}

export interface DecisionRecord {
  experiment_id?: string;
  id: string;
  timestamp: string;
  author: string;
  scenario_name: string;
  decision_type: string;
  expected_effect: string;
  status: string;
  parameters_summary: string;
  notes?: string;
}

export interface AppSettings {
  greenhouse_name: string;
  zone_name: string;
  crop: string;
  area_ha: number;
  timezone: string;
  temp_unit: string;
  radiation_unit: string;
  energy_unit: string;
  temp_min_critical: number;
  temp_max_critical: number;
  humidity_max_critical: number;
  vpd_min_critical: number;
  simulation_engine: string;
  is_live_control_blocked: boolean;
  safety_message: string;
}

export interface Calibration {
  version: string; created_at: string; dataset: string; source_kind: string;
  train_rows: number; test_rows: number; start: string; end: string; test_start: string;
  metrics: Record<string, {mae: number | null; baseline_mae: number | null; test_points: number}>;
  predictions: {time: string; fact: number; forecast: number}[]; method: string;
}
export interface ModelStatus {
  timezone: string;
  filename: string; source_kind: string; total_rows: number; start: string; end: string;
  model_name: string; model_status: string; hardware_control: boolean;
  calibration: Calibration | null; versions: Calibration[];
}
export interface ForecastFact { points: {time: string; fact: number | null; forecast: number}[]; matched_points: number; mae: number | null; }

export interface CropModelMetrics {
  humidity_mae: number;
  temperature_mae: number;
  light_mae: number;
}

export interface CropModelInfo {
  status: string;
  model_name: string;
  dataset_file: string;
  dataset_rows: number;
  available_crops: string[];
  metrics: CropModelMetrics;
}

export interface CropPredictionResult {
  crop: string;
  requested_crop: string;
  humidity: number;
  temperature: number;
  light_lux: number;
  light_umol: number;
  recommended_scenario: ScenarioEquipmentParams;
  metrics: CropModelMetrics;
}
