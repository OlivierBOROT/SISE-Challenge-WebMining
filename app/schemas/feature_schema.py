from dataclasses import dataclass


@dataclass
class InputFeatureSet:
    features: dict[str, float]
    vector: list[float]

@dataclass
class BehaviourFeatureSet:
    features: dict[str, float]
    vector: list[float]