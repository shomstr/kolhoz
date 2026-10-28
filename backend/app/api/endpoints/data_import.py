from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from app.models.schemas import DataQualityReport, GreenhousePassport, ColumnMapping
from app.services.data_service import DataService
from app.core.config import SAMPLE_CSV_PATH
from app.services.dataset_service import dataset_service
from app.db.store import store

router = APIRouter(prefix="/data", tags=["data"])
data_service = DataService()

@router.post("/upload", response_model=DataQualityReport)
async def upload_dataset(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Размер CSV не должен превышать 10 МБ.")
    try:
        report = data_service.analyze_uploaded_file(
            content,
            file.filename or "upload.csv",
            data_service.get_column_mapping(),
        )
        dataset_service.stage(content, file.filename or "upload.csv")
        try:
            report.valid_rows = dataset_service.activate(report.column_mapping)
            report.applied = True
        except ValueError as exc:
            report.validation_messages.append(str(exc))
        store.set("quality_report", report.model_dump())
        return report
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/sample-csv")
def download_sample_csv():
    data_service._ensure_sample_csv()
    return FileResponse(
        path=SAMPLE_CSV_PATH,
        filename="sample_greenhouse_log.csv",
        media_type="text/csv"
    )

@router.get("/quality-default", response_model=DataQualityReport)
def get_default_quality():
    saved = store.get("quality_report")
    if saved:
        return DataQualityReport.model_validate(saved)
    data_service._ensure_sample_csv()
    with open(SAMPLE_CSV_PATH, "rb") as f:
        content = f.read()
    if not store.get("pending_dataset"):
        dataset_service.stage(content, "sample_greenhouse_log.csv", "sample")
    report = data_service.analyze_uploaded_file(content, "sample_greenhouse_log.csv")
    report.applied = True
    report.valid_rows = report.total_rows
    return report

@router.get("/passport", response_model=GreenhousePassport)
def get_passport():
    return data_service.get_passport()

@router.post("/passport", response_model=GreenhousePassport)
def update_passport(passport: GreenhousePassport):
    return data_service.update_passport(passport)

@router.get("/mapping", response_model=ColumnMapping)
def get_column_mapping():
    return data_service.get_column_mapping()

@router.post("/mapping", response_model=ColumnMapping)
def update_column_mapping(mapping: ColumnMapping):
    try:
        rows = dataset_service.activate(mapping)
        pending = store.get("pending_dataset")
        import pandas as pd
        content = pd.DataFrame(pending["rows"]).to_csv(index=False).encode("utf-8")
        report = data_service.analyze_uploaded_file(content, pending["filename"], mapping)
        report.applied = True
        report.valid_rows = rows
        store.set("quality_report", report.model_dump())
        return data_service.update_column_mapping(mapping)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
