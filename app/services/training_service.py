"""
Training Service
Builds, trains and persists an anomaly detection model from FeatureSet vectors,
and exposes predict() for bot detection at inference time.

Supported models (AnomalyModel enum):
    ISOLATION_FOREST  — best for high-dimensional data, fast, robust
    LOF               — Local Outlier Factor, density-based, good for tight clusters
    ONE_CLASS_SVM     — kernel-based, effective but slower on large datasets

All hyper-parameters are controlled via ModelConfig, so nothing is hard-coded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import joblib
from sklearn.base import BaseEstimator
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM

from app.services.feature_service import FeatureSet, FEATURE_COLUMNS, to_numpy
from app.services.storage_service import load_numpy, record_count, JSONL_PATH

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

N_FEATURES = len(FEATURE_COLUMNS)   # must stay in sync with feature_service
_MODELS_DIR = Path(__file__).parent.parent / "models"


# ─────────────────────────────────────────────────────────────────────────────
# Model registry
# ─────────────────────────────────────────────────────────────────────────────

class AnomalyModel(str, Enum):
    ISOLATION_FOREST = "isolation_forest"
    LOF              = "lof"
    ONE_CLASS_SVM    = "one_class_svm"


# Default hyper-parameters per model type.
# Override any of these via ModelConfig.params.
_DEFAULTS: dict[AnomalyModel, dict[str, Any]] = {
    AnomalyModel.ISOLATION_FOREST: {
        "n_estimators":  200,
        "contamination": 0.08,
        "random_state":  42,
    },
    AnomalyModel.LOF: {
        "n_neighbors":   20,
        "contamination": 0.08,
        "novelty":       True,   # required for predict() on unseen data
    },
    AnomalyModel.ONE_CLASS_SVM: {
        "kernel": "rbf",
        "nu":     0.08,          # upper bound on the fraction of outliers
        "gamma":  "scale",
    },
}

# Decision-function scale differs across models.
# confidence = min(1.0, |score| / divisor)
_CONF_DIVISOR: dict[AnomalyModel, float] = {
    AnomalyModel.ISOLATION_FOREST: 0.15,
    AnomalyModel.LOF:              0.30,
    AnomalyModel.ONE_CLASS_SVM:    0.50,
}


# ─────────────────────────────────────────────────────────────────────────────
# Model configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ModelConfig:
    """
    Fully describes which model to train and with which hyper-parameters.

    Example — override contamination only:
        ModelConfig(AnomalyModel.ISOLATION_FOREST, params={"contamination": 0.05})

    Example — switch to LOF with custom neighbors:
        ModelConfig(AnomalyModel.LOF, params={"n_neighbors": 30})
    """
    model_type: AnomalyModel = AnomalyModel.ISOLATION_FOREST
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def resolved_params(self) -> dict[str, Any]:
        """Merge defaults with any caller-supplied overrides."""
        return {**_DEFAULTS[self.model_type], **self.params}

    @property
    def model_path(self) -> Path:
        """Each model type gets its own file so they don't overwrite each other."""
        return _MODELS_DIR / f"{self.model_type.value}.joblib"


# Shared default — change this once to switch the whole app.
DEFAULT_CONFIG = ModelConfig(AnomalyModel.ISOLATION_FOREST)


# ─────────────────────────────────────────────────────────────────────────────
# Model factory
# ─────────────────────────────────────────────────────────────────────────────

def _build_model(config: ModelConfig) -> BaseEstimator:
    """Instantiate the sklearn estimator described by config (unfitted)."""
    p = config.resolved_params
    match config.model_type:
        case AnomalyModel.ISOLATION_FOREST:
            return IsolationForest(**p)
        case AnomalyModel.LOF:
            return LocalOutlierFactor(**p)
        case AnomalyModel.ONE_CLASS_SVM:
            return OneClassSVM(**p)
        case _:
            raise ValueError(f"Unknown model type: {config.model_type}")


# ─────────────────────────────────────────────────────────────────────────────
# Output schema
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DetectionResult:
    session_id: str
    label: str          # "human" | "bot"
    score: float        # raw decision_function score (positive = human)
    anomaly: int        # 1 = normal (human), -1 = anomaly (bot)
    confidence: float   # 0.0–1.0
    model_type: str     # which model produced this result
    schema_version: str = "1.0"  # detection output schema version
    feature_version: str = "1.0"  # feature extraction schema version


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic training data
# ─────────────────────────────────────────────────────────────────────────────

def _generate_human_samples(n: int = 600, seed: int = _RANDOM_STATE) -> np.ndarray:
    """
    Generate n synthetic human-like feature vectors.
    Distributions are calibrated to match realistic browsing behavior.
    Column order must match FEATURE_COLUMNS exactly.
    """
    rng = np.random.default_rng(seed)

    # fmt: off
    samples = np.column_stack([
        # A — Mouse movement
        rng.uniform(1.5, 3.0, n),                              # entropy_direction
        rng.uniform(1.2, 2.8, n),                              # entropy_speed
        rng.lognormal(-4.5, 0.8, n),                           # speed_variance
        rng.lognormal(-3.0, 0.6, n),                           # max_speed
        rng.lognormal(-5.5, 0.9, n),                           # mean_acceleration
        rng.beta(2, 5, n),                                     # path_efficiency (human < 1)
        rng.integers(10, 60, n).astype(float),                 # direction_changes
        rng.uniform(0.3, 1.2, n),                              # mean_turning_angle
        rng.uniform(0.2, 0.8, n),                              # std_turning_angle
        rng.beta(1.5, 8, n),                                   # constant_speed_ratio (human low)
        rng.integers(0, 3, n).astype(float),                   # teleport_count

        # B — Clicks
        rng.beta(2, 7, n),                                     # click_move_ratio (human low)
        rng.uniform(0.15, 2.5, n),                             # interclick_min
        rng.lognormal(-1.0, 0.6, n),                           # interclick_std
        rng.uniform(0.08, 0.35, n),                            # click_hold_mean
        rng.integers(0, 2, n).astype(float),                   # rapid_burst_count
        rng.beta(1, 8, n),                                     # identical_interval_ratio (human low)

        # C — Forms
        rng.uniform(1.0, 6.0, n),                              # field_min_duration
        rng.uniform(2.0, 8.0, n),                              # field_avg_duration
        rng.integers(1, 6, n).astype(float),                   # fields_filled

        # D — Scroll
        rng.uniform(0.25, 0.90, n),                            # scroll_depth_max
        rng.uniform(0.5, 3.0, n),                              # scroll_event_rate
        rng.integers(1, 8, n).astype(float),                   # scroll_direction_changes

        # E — Session / Navigation
        rng.lognormal(3.5, 0.7, n),                            # session_duration (>10s)
        rng.integers(1, 6, n).astype(float),                   # pages_visited
        rng.beta(1.5, 6, n),                                   # revisit_rate
        rng.uniform(0.05, 0.6, n),                             # scroll_click_ratio
    ])
    # fmt: on

    assert samples.shape == (n, N_FEATURES), (
        f"Shape mismatch: got {samples.shape}, expected ({n}, {N_FEATURES}). "
        "Check _generate_human_samples() column count matches FEATURE_COLUMNS."
    )
    return samples


# ─────────────────────────────────────────────────────────────────────────────
# Train
# ─────────────────────────────────────────────────────────────────────────────

def train(
    config: ModelConfig = DEFAULT_CONFIG,
    feature_sets: list[FeatureSet] | None = None,
    use_stored: bool = True,
    n_synthetic: int = 600,
) -> BaseEstimator:
    """
    Train the anomaly detection model described by config.

    Data priority (all sources are stacked together):
    1. `feature_sets`  — FeatureSet objects passed directly (e.g. from the current session)
    2. `use_stored`    — records accumulated in data/features.jsonl via storage_service.append()
    3. `n_synthetic`   — synthetic human samples to pad / bootstrap cold-start

    Args:
        config:        ModelConfig specifying model type and hyper-parameters.
        feature_sets:  Optional list of FeatureSet objects (assumed human samples).
        use_stored:    If True, load all records from the JSONL store and include them.
        n_synthetic:   Number of synthetic human samples to add. Set to 0 to
                       train on real data only (requires feature_sets or use_stored).

    Returns:
        Fitted estimator.
    """
    parts: list[np.ndarray] = []

    if feature_sets:
        real = np.vstack([to_numpy(fs) for fs in feature_sets])  # (n, N_FEATURES)
        parts.append(real)

    if use_stored:
        n = record_count(JSONL_PATH)
        if n > 0:
            parts.append(load_numpy(JSONL_PATH))
            print(f"[training_service] Loaded {n} stored records from {JSONL_PATH}")

    if n_synthetic > 0:
        parts.append(_generate_human_samples(n_synthetic))

    if not parts:
        raise ValueError(
            "No training data: provide feature_sets, set use_stored=True with existing data, "
            "or set n_synthetic > 0."
        )

    X = np.vstack(parts)
    model = _build_model(config)
    model.fit(X)
    print(f"[training_service] Trained {config.model_type.value} on {X.shape[0]} samples "
          f"with params: {config.resolved_params}")
    return model


# ─────────────────────────────────────────────────────────────────────────────
# Persist
# ─────────────────────────────────────────────────────────────────────────────

def save(model: BaseEstimator, config: ModelConfig = DEFAULT_CONFIG) -> None:
    """Serialize the trained model to disk (path is derived from config)."""
    path = config.model_path
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    print(f"[training_service] Model saved → {path}")


def load(config: ModelConfig = DEFAULT_CONFIG) -> BaseEstimator:
    """Load a previously serialized model from disk."""
    path = config.model_path
    if not path.exists():
        raise FileNotFoundError(
            f"No model found at {path}. Call train() and save() first."
        )
    return joblib.load(path)


# ─────────────────────────────────────────────────────────────────────────────
# Lazy singleton — used by predict() when no model is passed explicitly
# ─────────────────────────────────────────────────────────────────────────────

_model: BaseEstimator | None = None


def _get_model(config: ModelConfig = DEFAULT_CONFIG) -> BaseEstimator:
    """
    Return the cached model for the given config.
    On first call: load from disk if available, otherwise train on synthetic data.
    Note: the cache holds one model at a time. If you switch config at runtime,
    call reload_model() to invalidate the cache.
    """
    global _model
    if _model is None:
        if config.model_path.exists():
            _model = load(config)
        else:
            _model = train(config)
            save(_model, config)
    return _model


def reload_model(config: ModelConfig = DEFAULT_CONFIG) -> BaseEstimator:
    """Force-retrain and cache a fresh model, then save it."""
    global _model
    _model = train(config)
    save(_model, config)
    return _model


# ─────────────────────────────────────────────────────────────────────────────
# Predict
# ─────────────────────────────────────────────────────────────────────────────

def predict(
    feature_set: FeatureSet,
    model: BaseEstimator | None = None,
    config: ModelConfig = DEFAULT_CONFIG,
) -> DetectionResult:
    """
    Run bot detection on a single FeatureSet.

    Args:
        feature_set:  Output of feature_service.extract().
        model:        Optional pre-loaded estimator. Uses the lazy singleton if None.
        config:       ModelConfig used to resolve the confidence divisor and
                      model type tag. Ignored if model is passed explicitly
                      without a config — in that case pass config too.

    Returns:
        DetectionResult with label, raw score, anomaly flag, confidence, and model_type.
    """
    if model is None:
        model = _get_model(config)

    X = to_numpy(feature_set)                            # shape (1, N_FEATURES)
    anomaly: int = int(model.predict(X)[0])              # 1 = human, -1 = bot
    score: float = float(model.decision_function(X)[0])  # positive = human

    label = "human" if anomaly == 1 else "bot"
    divisor = _CONF_DIVISOR[config.model_type]
    confidence = min(1.0, abs(score) / divisor)

    return DetectionResult(
        session_id=feature_set.session_id,
        label=label,
        score=round(score, 6),
        anomaly=anomaly,
        confidence=round(confidence, 4),
        model_type=config.model_type.value,
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from app.schemas import (
        MouseBehaviorBatch, MovementMetrics, ClickMetrics,
        ScrollMetrics, HeuristicMetrics, FormMetrics, NavigationMetrics,
    )
    from app.services.feature_service import extract, make_batch  # type: ignore[attr-defined]

    # --- swap config here to test a different model ---
    config = ModelConfig(AnomalyModel.ISOLATION_FOREST)
    # config = ModelConfig(AnomalyModel.LOF, params={"n_neighbors": 30})
    # config = ModelConfig(AnomalyModel.ONE_CLASS_SVM, params={"nu": 0.05})

    print(f"Training {config.model_type.value} with params: {config.resolved_params}")
    model = train(config, n_synthetic=600, use_stored=False)
    save(model, config)
    print(f"Model saved → {config.model_path}")

    # Build test batches via feature_service's __main__ helper
    # (re-implemented inline here to avoid import-time side effects)
    def _make_fs(label: str) -> FeatureSet:
        is_bot = label == "bot"
        batch = MouseBehaviorBatch(
            session_id=f"test-{label}-001",
            page="/checkout",
            batch_t=1200.0 if is_bot else 10000.0,
            movement=MovementMetrics(
                total_move_events=4 if is_bot else 80,
                move_event_rate_hz=0.4 if is_bot else 8.0,
                mean_delta_time_sec=0.1, std_delta_time_sec=0.0 if is_bot else 0.05,
                min_delta_time_sec=0.1, max_delta_time_sec=0.1 if is_bot else 0.8,
                total_distance_rel=0.5, net_displacement_rel=0.5 if is_bot else 0.2,
                path_efficiency_ratio=0.99 if is_bot else 0.45,
                mean_speed_rel=0.02 if is_bot else 0.015,
                std_speed_rel=0.0 if is_bot else 0.008,
                max_speed_rel=0.02 if is_bot else 0.04, min_speed_rel=0.02 if is_bot else 0.002,
                mean_acceleration_rel=0.0 if is_bot else 0.003,
                std_acceleration_rel=0.0 if is_bot else 0.002,
                max_acceleration_rel=0.0 if is_bot else 0.01,
                mean_turning_angle_rad=0.0 if is_bot else 0.8,
                std_turning_angle_rad=0.0 if is_bot else 0.4,
                direction_changes_count=0 if is_bot else 25,
                micro_movements_ratio=0.0, zero_delta_ratio=0.0, jitter_index=0.0,
            ),
            clicks=ClickMetrics(
                total_click_events=3, left_click_count=3, right_click_count=0,
                middle_click_count=0, double_click_count=0,
                mean_click_interval_sec=0.01 if is_bot else 1.2,
                std_click_interval_sec=0.0 if is_bot else 0.6,
                min_click_interval_sec=0.01 if is_bot else 0.4,
                max_click_interval_sec=0.01 if is_bot else 2.5,
                mean_click_hold_sec=0.001 if is_bot else 0.12,
                std_click_hold_sec=0.0 if is_bot else 0.05,
                max_click_hold_sec=0.001 if is_bot else 0.25,
                rapid_click_burst_count=2 if is_bot else 0,
                identical_interval_ratio=1.0 if is_bot else 0.1,
            ),
            scroll=ScrollMetrics(
                total_scroll_events=0 if is_bot else 12,
                scroll_event_rate_hz=0.0 if is_bot else 1.2,
                mean_scroll_delta_rel=0.0 if is_bot else 0.08,
                std_scroll_delta_rel=0.0 if is_bot else 0.04,
                max_scroll_delta_rel=0.0 if is_bot else 0.2,
                scroll_direction_changes=0 if is_bot else 3,
                continuous_scroll_sequences=0 if is_bot else 2,
                mean_scroll_interval_sec=0.0 if is_bot else 0.8,
                scroll_depth_max=0.0 if is_bot else 0.72,
            ),
            heuristics=HeuristicMetrics(
                constant_speed_ratio=1.0 if is_bot else 0.1,
                linear_movement_ratio=0.99 if is_bot else 0.45,
                perfect_straight_lines_count=4 if is_bot else 0,
                teleport_event_count=0, event_uniformity_score=0.0,
                entropy_direction=0.0 if is_bot else 2.4,
                entropy_speed=0.0 if is_bot else 2.1,
            ),
            form=FormMetrics(
                fields_filled=2,
                field_avg_duration_sec=0.002 if is_bot else 3.5,
                field_min_duration_sec=0.001 if is_bot else 2.8,
                field_order=["email", "card"],
            ),
            navigation=NavigationMetrics(
                pages_visited=["/checkout"] if is_bot else ["/", "/product", "/checkout"],
                unique_pages=1 if is_bot else 3,
                revisit_rate=0.0,
                session_duration_sec=1.2 if is_bot else 42.0,
            ),
        )
        from app.services.feature_service import extract
        return extract(batch)

    print()
    for label in ["human", "bot"]:
        fs = _make_fs(label)
        result = predict(fs, model=model, config=config)
        icon = "🟢" if result.label == "human" else "🔴"
        print(
            f"{icon} [{label.upper():>5}]  "
            f"label={result.label:<6}  "
            f"score={result.score:+.4f}  "
            f"confidence={result.confidence:.2%}  "
            f"model={result.model_type}"
        )
