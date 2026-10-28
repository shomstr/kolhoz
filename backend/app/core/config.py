import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.environ.get("KOLHOZ_DB_PATH", str(DATA_DIR / "kolhoz.db")))
SAMPLE_CSV_PATH = DATA_DIR / "sample_greenhouse_log.csv"

PROJECT_NAME = "Регул"
PROJECT_SUBTITLE = "Цифровой двойник теплицы"
VERSION = "1.0.0-mvp"
MODEL_ENGINE_NAME = "Simplified Balance Heuristic (DEMO)"
MODEL_VERSION = "v1.2.4-demo"

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "*",
]
