import uuid

from dataclasses import dataclass, field
from typing import Optional

from app.schemas import FeatureSet, DetectionResult

@dataclass
class UserSession:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    input_features: Optional[FeatureSet] = None
    bot_prediction: Optional[DetectionResult] = None
    