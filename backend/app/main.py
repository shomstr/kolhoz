from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import PROJECT_NAME, PROJECT_SUBTITLE, VERSION, CORS_ORIGINS
from app.api.endpoints import (
    climate,
    experiments,
    data_import,
    economics,
    reports,
    settings,
    model,
)

app = FastAPI(
    title=f"{PROJECT_NAME} — {PROJECT_SUBTITLE}",
    version=VERSION,
    description="Платформа моделирования микроклимата теплицы, анализа энергопотребления и проведения виртуальных экспериментов."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(climate.router, prefix="/api")
app.include_router(experiments.router, prefix="/api")
app.include_router(data_import.router, prefix="/api")
app.include_router(economics.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(model.router, prefix="/api")

@app.get("/api/health")
def healthcheck():
    return {
        "status": "healthy",
        "service": PROJECT_NAME,
        "version": VERSION,
        "is_demo_mode": True,
        "real_hardware_control": "DISABLED"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
