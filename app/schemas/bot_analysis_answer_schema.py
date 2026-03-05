from dataclasses import dataclass

@dataclass
class DetectionResult:
    label: str          # "human" | "bot"
    score: float        # raw decision_function score (positive = human)
    anomaly: int        # 1 = normal (human), -1 = anomaly (bot)
    confidence: float   # 0.0–1.0
    model_type: str     # which model produced this result
    schema_version: str = "1.0"  # detection output schema version
    feature_version: str = "1.0"  # feature extraction schema version
