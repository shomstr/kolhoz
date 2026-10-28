import math
from app.models.schemas import EconomicsSummary, TariffConfig, SimulationRequest
from app.db.store import store

class EconomicsService:
    def get_tariffs(self):
        return TariffConfig.model_validate(store.get('tariffs', {}))

    def update_tariffs(self, tariffs):
        store.set('tariffs', tariffs.model_dump())
        return tariffs

    def get_summary(self, period='month'):
        from app.services.simulation_engine import PhysicsDemoSimulationEngine
        from app.services.data_service import DataService
        tariffs = self.get_tariffs()
        last_runs = store.get('experiment_history', [])
        last_request = last_runs[0].get('request') or {} if last_runs else {}
        request = SimulationRequest(horizon_hours=24, custom_scenario=last_runs[0].get('parameters') if last_runs else None, preset_baseline=last_request.get('preset_baseline'), preset_aggressive=last_request.get('preset_aggressive'))
        result = PhysicsDemoSimulationEngine().simulate(request, DataService().get_current_climate(), tariffs)
        multiplier = {'month': 30, 'quarter': 90, 'year': 365}[period]
        base, eco, aggressive = result.baseline_kpi, result.custom_kpi or result.eco_kpi, result.aggressive_kpi
        def cost(k): return round(k.total_cost_rub * multiplier, 0)
        resource_breakdown = []
        for label, field, unit in [('Тепло','heat_mwh','МВт·ч'), ('Электроэнергия','elec_mwh','МВт·ч')]:
            a,b,c = getattr(base,field),getattr(eco,field),getattr(aggressive,field)
            diff = lambda x: f'{(x-a)/a*100:+.1f}%' if a else '—'
            resource_breakdown.append({'resource':label,'unit':unit,'current':round(a*multiplier,1),'baseline_val':round(a*multiplier,1),'eco_val':round(b*multiplier,1),'aggressive_val':round(c*multiplier,1),'baseline_diff':'0%','eco_diff':diff(b),'aggressive_diff':diff(c)})
        structures=[]
        for name,k in [('Базовый',base),('Вариант A',eco),('Вариант B',aggressive)]:
            heat=k.heat_mwh*tariffs.heat_rate_rub_mwh*multiplier
            structures.append({'category':name,'heating':round(heat/1000,2),'lighting':round(max(0,cost(k)-heat)/1000,2),'ventilation':0,'other':0})
        savings=cost(base)-cost(eco)
        monthly_savings = (base.total_cost_rub-eco.total_cost_rub)*30
        payback = math.ceil(tariffs.implementation_cost_rub/monthly_savings) if monthly_savings > 0 and tariffs.implementation_cost_rub > 0 else None
        return EconomicsSummary(period=period, tariffs=tariffs, eco_savings_pct_heat=eco.heat_diff_pct, eco_savings_pct_elec=eco.elec_diff_pct, eco_monthly_savings_rub=savings, baseline_monthly_cost_rub=cost(base), eco_monthly_cost_rub=cost(eco), aggressive_monthly_cost_rub=cost(aggressive), modeled_projected_savings_rub=savings, historical_confirmed_savings_rub=0, payback_months_min=payback, payback_months_max=payback, cost_structure=structures, resource_breakdown=resource_breakdown)
