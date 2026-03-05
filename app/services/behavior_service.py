import os
import time
from typing import Any, Dict, List, Optional

from app.behavior_model import FeatureBuilder, ModelManager

DEFAULT_MODEL_PATH = os.path.join("data", "models", "behavior_analysis_model.joblib")


class BehaviorService:
    """Behavior service: wraps feature building and model prediction.

    Provides a thin layer on top of the feature builder and the ML ModelManager.
    It can build a `FeatureSet` from raw events and run predictions using the
    loaded model.
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = model_path
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found at {self.model_path}")
        self.model_manager = ModelManager.load(self.model_path)
        self.feature_builder = FeatureBuilder()

    def build_feature_set(
        self,
        events: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        page: Optional[str] = None,
    ):
        """Build a FeatureSet dataclass from raw event dicts.

        The FeatureSet contains the named features and an ordered vector according
        to `FEATURE_COLUMNS` so it can be directly persisted with StorageService
        or passed to the model.
        """
        current_time = time.time()
        features = self.feature_builder.build(events, current_time=current_time)
        vector = [float(features.get(col, 0.0)) for col in FEATURE_COLUMNS]
        fs = FeatureSet(
            session_id=session_id or "unknown",
            page=str(page or ""),
            batch_t=float((current_time * 1000) % 1_000_000),
            features=features,
            vector=vector,
        )
        return fs

    def predict_from_raw(
        self,
        events: List[Dict[str, Any]],
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build features from raw events and run model prediction.

        Returns a dict with keys: `label`, `features`, `feature_set`.
        """
        fs = self.build_feature_set(events, session_id=session_id)
        label = self.model_manager.predict(fs.features)
        return {"label": label, "features": fs.features, "feature_set": fs}

    # Renamed API: predict_from_raw_data
    def predict_from_raw_data(
        self, events: List[Dict[str, Any]], session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compatibility wrapper for older naming: build features then predict."""
        return self.predict_from_raw(events, session_id=session_id)

    def log_feature(
        self,
        events: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        page: Optional[str] = None,
        jsonl_path: Optional[str] = None,
    ) -> None:
        """Transform raw events to features and append to a JSONL file.

        Arguments:
            events: raw event dicts (matching event_behavior_schema)
            session_id: optional session identifier
            page: optional page id/number
            jsonl_path: optional path to JSONL file (defaults to data/behavior_features.jsonl)
        """
        import json
        from datetime import datetime
        from pathlib import Path

        fs = self.build_feature_set(events, session_id=session_id, page=page)
        if jsonl_path is None:
            jsonl_path = Path("data") / "behavior_features.jsonl"
        else:
            jsonl_path = Path(jsonl_path)
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        row = {
            "session_id": fs.session_id,
            "page": fs.page,
            "batch_t": fs.batch_t,
            "features": fs.features,
            "vector": fs.vector,
            "stored_at": datetime.utcnow().isoformat(),
            "source": "behavior_service",
        }

        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
