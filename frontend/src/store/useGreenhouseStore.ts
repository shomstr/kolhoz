import { create } from 'zustand';
import { NavigationPage, ScenarioEquipmentParams, SimulationResult, ClimateCurrent } from '../types';

interface GreenhouseState {
  activePage: NavigationPage;
  setActivePage: (page: NavigationPage) => void;
  selectedZoneId: string;
  setSelectedZoneId: (zoneId: string) => void;
  apiStatus: 'checking' | 'online' | 'offline';
  setApiStatus: (status: 'checking' | 'online' | 'offline') => void;
  isSidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  currentClimate: ClimateCurrent | null;
  setCurrentClimate: (climate: ClimateCurrent) => void;
  
  // Эксперименты
  simulationHorizon: number; // 6–24 часа
  setSimulationHorizon: (hours: number) => void;
  selectedPreset: string; // "Базовый сценарий", "Экономичный сценарий", "Агрессивный сценарий", "Пользовательский"
  setSelectedPreset: (preset: string) => void;
  customParams: ScenarioEquipmentParams;
  setCustomParams: (params: Partial<ScenarioEquipmentParams>) => void;
  savedScenarios: ScenarioEquipmentParams[];
  setSavedScenarios: (scenarios: ScenarioEquipmentParams[]) => void;
  saveScenario: (scenario: ScenarioEquipmentParams) => void;
  simulationResult: SimulationResult | null;
  setSimulationResult: (result: SimulationResult | null) => void;
  isSimulating: boolean;
  setIsSimulating: (isSim: boolean) => void;
  
  // Уведомления / Тосты
  notification: string | null;
  notificationKind: 'success' | 'error';
  setNotification: (msg: string | null, kind?: 'success' | 'error') => void;
}

export const useGreenhouseStore = create<GreenhouseState>((set) => ({
  activePage: (() => {
    const page = typeof window === 'undefined' ? '' : window.location.hash.replace(/^#\/?/, '');
    return ['overview', 'climate', 'experiments', 'data', 'economics', 'reports', 'settings'].includes(page)
      ? page as NavigationPage
      : 'overview';
  })(),
  setActivePage: (page) => set({ activePage: page }),
  selectedZoneId: 'zone_a',
  setSelectedZoneId: (zoneId) => set({ selectedZoneId: zoneId }),
  apiStatus: 'checking',
  setApiStatus: (status) => set({ apiStatus: status }),
  isSidebarOpen: false,
  setSidebarOpen: (open) => set({ isSidebarOpen: open }),
  currentClimate: null,
  setCurrentClimate: (climate) => set({ currentClimate: climate }),

  simulationHorizon: 24,
  setSimulationHorizon: (hours) => set({ simulationHorizon: hours }),
  selectedPreset: 'Базовый сценарий',
  setSelectedPreset: (preset) => set({ selectedPreset: preset }),
  customParams: {
    name: 'Пользовательский сценарий',
    heating_temp: 22.0,
    vent_min_open: 10.0,
    screen_mode: 'auto_day_night',
    lighting_intensity: 300.0,
    co2_target: 800.0,
    night_temp_drop: 2.0,
  },
  setCustomParams: (params) =>
    set((state) => ({ customParams: { ...state.customParams, ...params } })),
  savedScenarios: (() => {
    try {
      const stored = typeof window === 'undefined' ? null : window.localStorage.getItem('kolhoznik-scenarios');
      return stored ? JSON.parse(stored) as ScenarioEquipmentParams[] : [];
    } catch {
      return [];
    }
  })(),
  setSavedScenarios: (savedScenarios) => {
    try { window.localStorage.setItem('kolhoznik-scenarios', JSON.stringify(savedScenarios)); } catch { /* local saving can be disabled by the browser */ }
    set({ savedScenarios });
  },
  saveScenario: (scenario) => set((state) => {
    const savedScenarios = [scenario, ...state.savedScenarios.filter((item) => item.name !== scenario.name)];
    try { window.localStorage.setItem('kolhoznik-scenarios', JSON.stringify(savedScenarios)); } catch { /* local saving can be disabled by the browser */ }
    return { savedScenarios };
  }),
  simulationResult: null,
  setSimulationResult: (result) => set({ simulationResult: result }),
  isSimulating: false,
  setIsSimulating: (isSim) => set({ isSimulating: isSim }),

  notification: null,
  notificationKind: 'success',
  setNotification: (msg, kind='success') => set({ notification: msg, notificationKind:kind }),
}));
