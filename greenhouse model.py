from pathlib import Path
import catboost as cb
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / 'greenhouse_dataset_500.csv'

if not DATASET_PATH.exists():
    DATASET_PATH = Path('greenhouse_dataset_500.csv')

df = pd.read_csv(DATASET_PATH)

X = df[['Культура']].copy()
y = df[['влажность', 'температура', 'светлость']].copy()

le = LabelEncoder()
X['Культура_encoded'] = le.fit_transform(X['Культура'])
X_features = X[['Культура_encoded']]

X_train, X_test, y_train, y_test = train_test_split(
    X_features, y, test_size=0.2, random_state=42
)

models = {}
targets = ['влажность', 'температура', 'светлость']

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
    models[target] = model


def normalize_crop_name(name: str) -> str:
    cleaned = name.strip()
    lower = cleaned.lower()
    if any(w in lower for w in ['томат', 'помидор']):
        return 'Помидоры'
    if any(w in lower for w in ['огур']):
        return 'Огурцы'
    if any(w in lower for w in ['кабач']):
        return 'Кабачки'
    return cleaned.capitalize()


def predict_greenhouse_climate(crop_name):
    normalized = normalize_crop_name(crop_name)
    if normalized not in le.classes_:
        available = ', '.join(le.classes_)
        return f"Культура '{crop_name}' не найдена. Доступны: {available}"

    encoded_val = le.transform([normalized])[0]
    input_data = pd.DataFrame([[encoded_val]], columns=['Культура_encoded'])

    pred_humidity = float(models['влажность'].predict(input_data)[0])
    pred_temp = float(models['температура'].predict(input_data)[0])
    pred_light = float(models['светлость'].predict(input_data)[0])

    return {
        'Культура': normalized,
        'Влажность (%)': round(pred_humidity, 1),
        'Температура (°C)': round(pred_temp, 1),
        'Светлость (лк)': int(round(pred_light, -1)),
    }


if __name__ == '__main__':
    print("Модель CatBoost для прогнозирования микроклимата теплицы загружена.")
    print("Доступные культуры: " + ", ".join(le.classes_))
    while True:
        try:
            user_input = input('\nВведите название культуры (или "выход"): ').strip()
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.lower() in ['выход', 'exit', 'quit']:
            break

        if not user_input:
            continue

        result = predict_greenhouse_climate(user_input)

        if isinstance(result, dict):
            for key, value in result.items():
                print(f'  • {key}: {value}')
        else:
            print(result)