"""Service for crop-based greenhouse climate prediction using CatBoost regressors."""
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error
import catboost as cb


class CropModelService:
    def __init__(self):
        self._dataset_path = self._resolve_dataset_path()
        self._models: Dict[str, cb.CatBoostRegressor] = {}
        self._label_encoder: Optional[LabelEncoder] = None
        self._available_crops: List[str] = []
        self._metrics: Dict[str, float] = {}
        self._dataset_rows: int = 0
        self._is_trained: bool = False

    def _resolve_dataset_path(self) -> Path:
        """Find the greenhouse_dataset_500.csv file in common locations."""
        candidates = [
            Path(__file__).resolve().parents[3] / "greenhouse_dataset_500.csv",  # Repo root
            Path(__file__).resolve().parents[2] / "data" / "greenhouse_dataset_500.csv",  # backend/data
            Path.cwd() / "greenhouse_dataset_500.csv",
            Path.cwd().parent / "greenhouse_dataset_500.csv",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        # Default fallback
        return candidates[0]

    def _ensure_trained(self):
        if self._is_trained:
            return

        if not self._dataset_path.exists():
            raise FileNotFoundError(f"Файл датасета {self._dataset_path.name} не найден.")

        df = pd.read_csv(self._dataset_path)
        self._dataset_rows = len(df)

        X = df[['Культура']].copy()
        y = df[['влажность', 'температура', 'светлость']].copy()

        self._label_encoder = LabelEncoder()
        X['Культура_encoded'] = self._label_encoder.fit_transform(X['Культура'])
        self._available_crops = sorted(list(self._label_encoder.classes_))

        X_features = X[['Культура_encoded']]

        X_train, X_test, y_train, y_test = train_test_split(
            X_features, y, test_size=0.2, random_state=42
        )

        targets = ['влажность', 'температура', 'светлость']
        self._models = {}
        self._metrics = {}

        for target in targets:
            model = cb.CatBoostRegressor(
                iterations=300,
                learning_rate=0.05,
                depth=4,
                loss_function='RMSE',
                verbose=0,
                random_seed=42,
            )
            model.fit(X_train, y_train[target])
            self._models[target] = model

            # Validation metrics
            preds = model.predict(X_test)
            mae = float(mean_absolute_error(y_test[target], preds))
            self._metrics[f"{target}_mae"] = round(mae, 3)

        self._is_trained = True

    def normalize_crop_name(self, raw_name: str) -> str:
        """Resolve common crop aliases and variations to dataset labels."""
        raw_clean = raw_name.strip()
        lower = raw_clean.lower()

        if any(w in lower for w in ['томат', 'помидор']):
            return 'Помидоры'
        if any(w in lower for w in ['огур']):
            return 'Огурцы'
        if any(w in lower for w in ['кабач']):
            return 'Кабачки'

        # Default capitalization match
        capitalized = raw_clean.capitalize()
        if capitalized in self._available_crops:
            return capitalized

        # Try match if crop string starts with or contains known crop
        for known in self._available_crops:
            if known.lower() in lower or lower in known.lower():
                return known

        return capitalized

    def get_info(self) -> Dict[str, Any]:
        self._ensure_trained()
        return {
            "status": "ready",
            "model_name": "CatBoostRegressor (Культура -> Климат)",
            "dataset_file": self._dataset_path.name,
            "dataset_rows": self._dataset_rows,
            "available_crops": self._available_crops,
            "metrics": {
                "humidity_mae": self._metrics.get("влажность_mae", 0.0),
                "temperature_mae": self._metrics.get("температура_mae", 0.0),
                "light_mae": self._metrics.get("светлость_mae", 0.0),
            },
        }

    def predict(self, crop_name: str) -> Dict[str, Any]:
        self._ensure_trained()
        resolved_crop = self.normalize_crop_name(crop_name)

        if resolved_crop not in self._label_encoder.classes_:
            raise ValueError(
                f"Культура '{crop_name}' не найдена в обученной модели. "
                f"Доступные культуры: {', '.join(self._available_crops)}"
            )

        encoded_val = self._label_encoder.transform([resolved_crop])[0]
        input_data = pd.DataFrame([[encoded_val]], columns=['Культура_encoded'])

        pred_humidity = float(self._models['влажность'].predict(input_data)[0])
        pred_temp = float(self._models['температура'].predict(input_data)[0])
        pred_light = float(self._models['светлость'].predict(input_data)[0])

        # Lux to approximate PAR (µmol/m²·s) for greenhouse lighting
        approx_umol = round(pred_light * 0.02, 1)

        return {
            "crop": resolved_crop,
            "requested_crop": crop_name,
            "humidity": round(pred_humidity, 1),
            "temperature": round(pred_temp, 1),
            "light_lux": int(round(pred_light, -1)),
            "light_umol": approx_umol,
            "recommended_scenario": {
                "name": f"ML: {resolved_crop}",
                "heating_temp": round(pred_temp, 1),
                "vent_min_open": 10.0 if pred_humidity < 80 else 15.0,
                "screen_mode": "auto_day_night",
                "lighting_intensity": approx_umol,
                "co2_target": 800.0,
                "night_temp_drop": 2.0,
            },
            "metrics": self.get_info()["metrics"],
        }


crop_model_service = CropModelService()
