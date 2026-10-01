from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


MODEL_DIR = Path(__file__).resolve().parent / "models"


@lru_cache(maxsize=None)
def load_model(model_name: str) -> Any:
    model_path = MODEL_DIR / model_name
    if not model_path.is_file():
        raise FileNotFoundError(f"Model artifact not found: {model_path}")
    return joblib.load(model_path)


def predict(model_name: str, values: dict[str, Any]) -> Any:
    model = load_model(model_name)
    features = dict(values)

    if model_name == "random_forest_model.pkl":
        date = pd.to_datetime(features.pop("Planting Date"), errors="raise")
        features.update(
            {
                "Planting_Year": date.year,
                "Planting_Month": date.month,
                "Planting_Day": date.day,
                "Planting_DayOfYear": date.dayofyear,
                "Planting_Quarter": date.quarter,
            }
        )
    elif model_name == "price_prediction_model.pkl":
        features["month"] = pd.to_datetime(features["month"], errors="raise").month

    expected_columns = getattr(model, "feature_names_in_", None)
    if expected_columns is not None:
        features = {column: features.get(column) for column in expected_columns}

    result = model.predict(pd.DataFrame([features]))[0]
    return result.item() if hasattr(result, "item") else result
