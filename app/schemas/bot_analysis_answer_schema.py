from dataclasses import dataclass

@dataclass
class DetectionResult:
    label: str          # "human" | "bot"
    score: float        # bot probability (0 = human, 1 = bot)
    anomaly: int        # 1 = normal (human), -1 = anomaly (bot)
    confidence: float   # confidence in the predicted label (0.0–1.0)
    model_type: str     # which model produced this result
    persona: str = "unknown"    # decoded class label (e.g. "human", "bot_scan")
    schema_version: str = "1.0"  # detection output schema version
    feature_version: str = "1.0"  # feature extraction schema version


@dataclass
class ClusteringResult:
    label: int
    pc1: float
    pc2: float
    schema_version: str = "1.0"  # detection output schema version
    feature_version: str = "1.0"  # feature extraction schema version