import uuid

from dataclasses import dataclass, field
from typing import Optional

from app.schemas import InputFeatureSet, DetectionResult, UserEvents

@dataclass
class UserSession:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    input_features: Optional[InputFeatureSet] = None
    behaviour_features: Optional[dict] = None
    behaviour_window: UserEvents = field(default_factory=lambda: UserEvents(events=[]))
    bot_prediction: Optional[DetectionResult] = None
    behaviour_prediction: Optional[int] = None
    