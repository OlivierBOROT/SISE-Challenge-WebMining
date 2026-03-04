import os
import time
from typing import Any, Dict, List

from app.behavior_model import FeatureBuilder, ModelManager

DEFAULT_MODEL_PATH = os.path.join("data", "models", "behavior_analysis_model.joblib")


class BehaviorService:
    """Service that loads a saved ModelManager and exposes prediction from raw events.

    On initialization it attempts to load the model from `model_path`. If the file
    is missing a FileNotFoundError is raised.
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = model_path
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found at {self.model_path}")
        self.model_manager = ModelManager.load(self.model_path)
        self.feature_builder = FeatureBuilder()

    def predict_from_raw(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Transform raw events to features and predict cluster/label.

        Returns a dict with `label` and `features`.
        """
        current_time = time.time()
        features = self.feature_builder.build(events, current_time=current_time)
        label = self.model_manager.predict(features)
        return {"label": label, "features": features}
