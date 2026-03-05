from dataclasses import dataclass, field
import uuid


@dataclass
class InputFeatureSet:
    page: str
    batch_t: float
    features: dict[str, float]      # named features
    vector: list[float]             # ordered vector for the model
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))