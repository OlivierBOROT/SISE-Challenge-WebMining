import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.behavior_model import FeatureBuilder, ModelManager

DEFAULT_MODEL_PATH = os.path.join("data", "models", "behavior_analysis_model.joblib")


class BehaviorService:
    """BehaviorService: build features from raw events and predict/log them.

    This service explicitly uses `behavior_model.FeatureBuilder` to transform
    `event_behavior_schema`-shaped inputs into feature dicts, and `ModelManager`
    to predict cluster/label. It does NOT rely on `services/feature_service.py`.
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = model_path
        self.model_manager = None
        self.feature_builder = None

        if not os.path.exists(self.model_path):
            self.model_found = False
            print(
                f"Warning: Model file not found at {self.model_path}. Prediction will fail until a model is trained and saved at this path."
            )
        else:
            self.model_found = True
            self.model_manager = ModelManager.load(self.model_path)
        self.feature_builder = FeatureBuilder()

    def predict_from_raw_data(
        self, events: List[Dict[str, Any]], session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build features from raw events and return model prediction.

        Returns:
            dict: {"label": int, "features": Dict[str, float]}
        """
        if not self.model_found:
            raise RuntimeError(
                f"Model file not found at {self.model_path}. Cannot predict. Please train and save a model at this path."
            )
        current_time = time.time()
        features = self.feature_builder.build(events, current_time=current_time)
        label = self.model_manager.predict(features)
        return {"label": int(label), "features": features}

    def log_feature(
        self,
        events: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        page: Optional[int] = None,
        jsonl_path: Optional[str] = None,
    ) -> None:
        """Transform raw events to features and append one JSONL row.

        If `page` is not provided, the method will attempt to extract the last
        seen `page` event from `events` (object == "page" and key `page_num`).
        The default JSONL path is `data/behavior_features.jsonl`.
        """
        data_path = os.getenv("DATA_PATH", "data")
        if jsonl_path is None:
            jsonl_path = Path(data_path) / "features" / "behavior_features.jsonl"
        else:
            jsonl_path = Path(jsonl_path)

        jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        current_time = time.time()
        features = self.feature_builder.build(events, current_time=current_time)
        print("features", flush=True)
        print(features, flush=True)
        # Try to infer page number from events if not explicitly provided
        if page is None:
            for e in reversed(events):
                if e.get("object") == "page" and e.get("page_num") is not None:
                    try:
                        page = int(e.get("page_num"))
                        break
                    except Exception:
                        continue

        row = {
            "session_id": session_id or "unknown",
            "page": page if page is not None else None,
            "timestamp": datetime.utcnow().isoformat(),
            "features": features,
            "source": "behavior_service",
        }

        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
