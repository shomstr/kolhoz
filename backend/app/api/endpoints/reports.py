from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from app.models.schemas import DecisionRecord, CreateDecisionRequest
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])
report_service = ReportService()

@router.get("/decisions", response_model=List[DecisionRecord])
def get_decisions(status: Optional[str] = Query(None)):
    return report_service.get_decisions(status=status)

@router.post("/decisions", response_model=DecisionRecord)
def create_decision(req: CreateDecisionRequest):
    return report_service.add_decision(req)

@router.patch("/decisions/{id}/archive", response_model=DecisionRecord)
def archive_decision(id: str):
    try:
        return report_service.archive(id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
