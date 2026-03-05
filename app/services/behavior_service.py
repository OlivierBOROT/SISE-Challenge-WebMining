import logging
import os
import time
from typing import Any, Dict, List

from app.behavior_model import FeatureBuilder, ModelManager

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = os.path.join("data", "models", "behavior_analysis_model.joblib")


class BehaviorService:
    """Service that loads a saved ModelManager and exposes prediction from raw events.

    On initialization it attempts to load the model from `model_path`. If the file
    is missing a warning is logged and the service is disabled until the model is available.
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = model_path
        self.model_manager = None
        self.feature_builder = None
        
        if not os.path.exists(self.model_path):
            logger.warning(
                f"Behavior clustering model not found at {self.model_path}. "
                "This feature is disabled until the model is provided."
            )
        else:
            try:
                self.model_manager = ModelManager.load(self.model_path)
                self.feature_builder = FeatureBuilder()
                logger.info(f"Loaded behavior clustering model from {self.model_path}")
            except Exception as e:
                logger.error(f"Failed to load behavior model: {e}")

    def predict_from_raw(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Transform raw events to features and predict cluster/label.

        Returns a dict with `label` and `features`.
        Raises RuntimeError if model is not available.
        """
        if self.model_manager is None or self.feature_builder is None:
            raise RuntimeError(
                "Behavior clustering model is not available. "
                f"Model file required at: {self.model_path}"
            )
        
        current_time = time.time()
        features = self.feature_builder.build(events, current_time=current_time)
        label = self.model_manager.predict(features)
        return {"label": label, "features": features}
