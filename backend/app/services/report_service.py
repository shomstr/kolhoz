import uuid
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
from app.models.schemas import DecisionRecord, CreateDecisionRequest
from app.db.store import store

class ReportService:
    def get_decisions(self, status: Optional[str] = None):
        records = [DecisionRecord.model_validate(item) for item in store.get("decisions", []) if not item.get("scenario_name", "").startswith("DEMO")]
        return [record for record in records if not status or record.status == status]

    def add_decision(self, req: CreateDecisionRequest):
        record = DecisionRecord(id=f"dec-{uuid.uuid4().hex[:8]}", timestamp=datetime.now(ZoneInfo("Europe/Moscow")).isoformat(), author=req.author or "Агроном", scenario_name=req.scenario_name, experiment_id=req.experiment_id, decision_type="Виртуальный сценарий", expected_effect=req.expected_effect, status="Принято", parameters_summary=req.parameters_summary, notes=req.notes)
        store.set("decisions", [record.model_dump(), *[x.model_dump() for x in self.get_decisions()]])
        return record

    def archive(self, id: str):
        records = self.get_decisions()
        found = False
        for record in records:
            if record.id == id:
                record.status = "Архив"
                found = True
        if not found:
            raise ValueError("Решение не найдено.")
        store.set("decisions", [record.model_dump() for record in records])
        return next(record for record in records if record.id == id)
