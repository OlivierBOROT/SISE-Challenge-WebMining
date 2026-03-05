from dataclasses import dataclass

@dataclass
class InputFeatureSet:
    page: str
    batch_t: float
    features: dict[str, float]      # named features
    vector: list[float]             # ordered vector for the model