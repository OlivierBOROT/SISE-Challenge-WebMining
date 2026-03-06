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

import os

from app.schemas import DetectionResult
from app.input_model.feature_builder import FEATURE_COLUMNS, InputFeatureSet, to_numpy
from app.utility.storage import StorageService, load_numpy, record_count

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

N_FEATURES = len(FEATURE_COLUMNS)   # must stay in sync with feature_service
_MODELS_DIR = Path(os.environ.get("DATA_PATH", "data")) / "models"
_INPUT_FEATURES_JSONL = "features/input_features.jsonl"
_RANDOM_STATE = 42

# Supervised model paths (RandomForest pipeline + LabelEncoder)
_SUPERVISED_CLF_PATH = _MODELS_DIR / "supervised_input_classifier.joblib"
_SUPERVISED_LE_PATH  = _MODELS_DIR / "supervised_input_label_encoder.joblib"


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
        self._supervised_clf: Any = None
        self._supervised_le: Any = None
        self._try_load_supervised()
        logger.debug(f"Initializing TrainingService with config: {config.model_type.value}")

    def _try_load_supervised(self) -> bool:
        """Load supervised pipeline + label encoder if available. Returns True on success."""
        if _SUPERVISED_CLF_PATH.exists() and _SUPERVISED_LE_PATH.exists():
            try:
                self._supervised_clf = joblib.load(_SUPERVISED_CLF_PATH)
                self._supervised_le  = joblib.load(_SUPERVISED_LE_PATH)
                logger.info(f"Loaded supervised classifier from {_SUPERVISED_CLF_PATH}")
                return True
            except Exception as exc:
                logger.warning(f"Could not load supervised model: {exc}")
                self._supervised_clf = None
                self._supervised_le  = None
        return False

    def _predict_supervised(self, feature_set: InputFeatureSet) -> DetectionResult:
        """Predict using the supervised pipeline + label encoder."""
        X = to_numpy(feature_set)  # shape (1, N_FEATURES)

        encoded_pred = int(self._supervised_clf.predict(X)[0])
        persona: str = str(self._supervised_le.inverse_transform([encoded_pred])[0])

        label = "human" if persona == "human" else "bot"
        anomaly = 1 if label == "human" else -1

        # bot probability = probability of the class labelled "bot" (or first non-human class)
        classes = list(self._supervised_le.classes_)
        proba = self._supervised_clf.predict_proba(X)[0]
        # Handle both binary ("bot"/"human") and multi-class ("bot_scan", …) label sets
        bot_indices = [i for i, c in enumerate(classes) if c != "human"]
        bot_prob = float(sum(proba[i] for i in bot_indices))

        score = round(bot_prob, 6)
        confidence = round(score if label == "bot" else 1.0 - score, 4)

        return DetectionResult(
            label=label,
            score=score,
            anomaly=anomaly,
            confidence=confidence,
            model_type="supervised_rf",
            persona=persona,
        )

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

            # D — Scroll  (scroll_depth_max excluded — unreliable from JS timing)
            rng.uniform(0.5, 3.0, n),                              # scroll_event_rate
            rng.integers(1, 8, n).astype(float),                   # scroll_direction_changes

            # E — Session / Navigation  (session_duration excluded — leaks time info)
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
            _storage = StorageService(_INPUT_FEATURES_JSONL, InputFeatureSet)
            human_sets = _storage.load_feature_sets(source="human")
            if human_sets:
                parts.append(np.vstack([to_numpy(fs) for fs in human_sets]))
                logger.debug(f"Loaded {len(human_sets)} stored human records from {_INPUT_FEATURES_JSONL}")

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

        # Use supervised model when available (preferred path)
        if self._supervised_clf is not None:
            return self._predict_supervised(feature_set)

        if model is None:
            model = self.get_model(cfg)

        X = to_numpy(feature_set)
        anomaly: int = int(model.predict(X)[0])
        raw_score: float = float(model.decision_function(X)[0])
        # Normalise IF score to [0,1] where low = bot, high = human
        # Then invert so score = bot probability for UI consistency
        human_prob = (raw_score + 1) / 2
        score = round(1.0 - human_prob, 6)

        label = "human" if anomaly == 1 else "bot"
        divisor = _CONF_DIVISOR[cfg.model_type]
        confidence = round(min(1.0, abs(raw_score) / divisor), 4)

        return DetectionResult(
            label=label,
            score=score,
            anomaly=anomaly,
            confidence=confidence,
            model_type=cfg.model_type.value,
            persona=label,
        )

