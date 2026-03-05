"""
Training Service
Builds, trains and persists an anomaly detection model from InputFeatureSet vectors,
and exposes predict() for bot detection at inference time.

Supported models (AnomalyModel enum):
    ISOLATION_FOREST  — best for high-dimensional data, fast, robust
    LOF               — Local Outlier Factor, density-based, good for tight clusters
    ONE_CLASS_SVM     — kernel-based, effective but slower on large datasets

All hyper-parameters are controlled via ModelConfig, so nothing is hard-coded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM

from app.schemas import DetectionResult
from app.input_model.feature_builder import FEATURE_COLUMNS, InputFeatureSet, to_numpy
from app.services.storage_service import JSONL_PATH, load_numpy, record_count

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

N_FEATURES = len(FEATURE_COLUMNS)   # must stay in sync with feature_service
_MODELS_DIR = Path(__file__).parent.parent / "models"
_RANDOM_STATE = 42


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
# Training Service
# ─────────────────────────────────────────────────────────────────────────────


class InputModelManager:
    """
    Manages anomaly detection model training, persistence, and inference.
    Encapsulates model state and caching to support lazy-loading and retraining.
    """

    def __init__(self, storage=None, config: ModelConfig = DEFAULT_CONFIG):
        """
        Initialize training service.

        Args:
            storage: Optional StorageService instance for accessing training data
            config: ModelConfig specifying model type and hyper-parameters
        """
        self.storage = storage
        self.config = config
        self._model: BaseEstimator | None = None
        logger.debug(f"Initializing TrainingService with config: {config.model_type.value}")

    def _build_model(self, cfg: ModelConfig | None = None) -> BaseEstimator:
        """Instantiate the sklearn estimator described by config (unfitted)."""
        if cfg is None:
            cfg = self.config
        p = cfg.resolved_params
        match cfg.model_type:
            case AnomalyModel.ISOLATION_FOREST:
                return IsolationForest(**p)
            case AnomalyModel.LOF:
                return LocalOutlierFactor(**p)
            case AnomalyModel.ONE_CLASS_SVM:
                return OneClassSVM(**p)
            case _:
                raise ValueError(f"Unknown model type: {cfg.model_type}")

    def _generate_human_samples(self, n: int = 600, seed: int = _RANDOM_STATE) -> np.ndarray:
        """Generate n synthetic human-like feature vectors."""
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

    def train(
        self,
        feature_sets: list[InputFeatureSet] | None = None,
        use_stored: bool = True,
        n_synthetic: int = 600,
        cfg: ModelConfig | None = None,
    ) -> BaseEstimator:
        """
        Train the anomaly detection model.

        Args:
            feature_sets: Optional list of InputFeatureSet objects (assumed human samples)
            use_stored: If True, load records from data/features.jsonl
            n_synthetic: Number of synthetic human samples to add
            cfg: Optional ModelConfig. If None, uses self.config

        Returns:
            Fitted estimator
        """
        if cfg is None:
            cfg = self.config

        parts: list[np.ndarray] = []

        if feature_sets:
            real = np.vstack([to_numpy(fs) for fs in feature_sets])
            parts.append(real)

        if use_stored:
            n = record_count(JSONL_PATH)
            if n > 0:
                parts.append(load_numpy(JSONL_PATH))
                logger.debug(f"Loaded {n} stored records from {JSONL_PATH}")

        if n_synthetic > 0:
            parts.append(self._generate_human_samples(n_synthetic))

        if not parts:
            raise ValueError(
                "No training data: provide feature_sets, set use_stored=True with existing data, "
                "or set n_synthetic > 0."
            )

        X = np.vstack(parts)
        model = self._build_model(cfg)
        model.fit(X)
        logger.info(
            f"Trained {cfg.model_type.value} on {X.shape[0]} samples "
            f"with params: {cfg.resolved_params}"
        )
        return model

    def save(self, model: BaseEstimator | None = None, cfg: ModelConfig | None = None) -> None:
        """
        Serialize the trained model to disk.

        Args:
            model: Optional model to save. If None, saves self._model
            cfg: Optional ModelConfig. If None, uses self.config
        """
        if model is None:
            model = self._model
        if model is None:
            raise ValueError("No model to save. Train or load a model first.")

        if cfg is None:
            cfg = self.config

        path = cfg.model_path
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, path)
        logger.info(f"Model saved → {path}")

    def load(self, cfg: ModelConfig | None = None) -> BaseEstimator:
        """
        Load a previously serialized model from disk.

        Args:
            cfg: Optional ModelConfig. If None, uses self.config

        Returns:
            Loaded estimator
        """
        if cfg is None:
            cfg = self.config

        path = cfg.model_path
        if not path.exists():
            raise FileNotFoundError(
                f"No model found at {path}. Call train() and save() first."
            )
        self._model = joblib.load(path)
        logger.debug(f"Loaded model from {path}")
        return self._model

    def get_model(self, cfg: ModelConfig | None = None) -> BaseEstimator:
        """
        Return the cached model.
        On first call: load from disk if available, otherwise train on synthetic data.

        Args:
            cfg: Optional ModelConfig. If None, uses self.config

        Returns:
            Estimator (loaded or trained)
        """
        if cfg is None:
            cfg = self.config

        if self._model is None:
            if cfg.model_path.exists():
                self._model = self.load(cfg)
            else:
                self._model = self.train(cfg=cfg)
                self.save(self._model, cfg)
        return self._model

    def reload_model(self, cfg: ModelConfig | None = None) -> BaseEstimator:
        """
        Force-retrain and cache a fresh model, then save it.

        Args:
            cfg: Optional ModelConfig. If None, uses self.config

        Returns:
            Newly trained estimator
        """
        if cfg is None:
            cfg = self.config

        self._model = self.train(cfg=cfg)
        self.save(self._model, cfg)
        return self._model

    def predict(
        self,
        feature_set: InputFeatureSet,
        model: BaseEstimator | None = None,
        cfg: ModelConfig | None = None,
    ) -> DetectionResult:
        """
        Run bot detection on a single InputFeatureSet.

        Args:
            feature_set: Output of feature_service.extract()
            model: Optional pre-loaded estimator. Uses get_model() if None
            cfg: Optional ModelConfig. If None, uses self.config

        Returns:
            DetectionResult with label, score, anomaly, confidence, model_type
        """
        if cfg is None:
            cfg = self.config

        if model is None:
            model = self.get_model(cfg)

        X = to_numpy(feature_set)
        anomaly: int = int(model.predict(X)[0])
        score: float = float(model.decision_function(X)[0])

        label = "human" if anomaly == 1 else "bot"
        divisor = _CONF_DIVISOR[cfg.model_type]
        confidence = min(1.0, abs(score) / divisor)

        return DetectionResult(
            label=label,
            score=round(score, 6),
            anomaly=anomaly,
            confidence=round(confidence, 4),
            model_type=cfg.model_type.value,
        )

