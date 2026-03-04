"""
Feature Service
Receives a validated MouseBehaviorBatch and produces a normalized feature
vector ready to be passed to the ML model.
"""

import logging
import math
from dataclasses import dataclass

import numpy as np

from app.schemas import MouseBehaviorBatch

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Ordered feature vector — order must remain stable for the model
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_COLUMNS = [
    # A — Mouse movement
    "entropy_direction",          # Shannon over directions   — bot linear → 0
    "entropy_speed",              # Shannon over speeds       — bot constant → 0
    "speed_variance",             # speed std dev             — bot constant → 0
    "max_speed",                  # max speed                 — bot may exceed threshold
    "mean_acceleration",          # mean acceleration         — interpolated bot → 0
    "path_efficiency",            # net dist / total dist     — bot → 1.0
    "direction_changes",          # number of direction changes
    "mean_turning_angle",         # mean angle between segments
    "std_turning_angle",          # angle variance            — bot → 0
    "constant_speed_ratio",       # % of constant-speed segments — bot → 1
    "teleport_count",             # abnormally fast movements

    # B — Clicks
    "click_move_ratio",           # clicks / movements        — headless → high
    "interclick_min",             # min delay between clicks  — bot < 50ms
    "interclick_std",             # inter-click variance      — bot → 0
    "click_hold_mean",            # mean click hold duration  — bot → 0
    "rapid_burst_count",          # rapid click bursts
    "identical_interval_ratio",   # repeated identical delays — bot → 1

    # C — Forms
    "field_min_duration",         # min fill duration (sec)   — bot ≈ 0
    "field_avg_duration",         # mean fill duration (sec)
    "fields_filled",              # number of fields touched

    # D — Scroll
    "scroll_depth_max",           # max scroll depth reached  — headless → 0
    "scroll_event_rate",          # scroll frequency
    "scroll_direction_changes",   # direction reversals       — bot → 0

    # E — Session / Navigation
    "session_duration",           # total duration (sec)      — bot → very short
    "pages_visited",              # number of pages visited
    "revisit_rate",               # revisit rate              — bot → 0
    "scroll_click_ratio",         # scroll / clicks           — headless → 0
]


# ─────────────────────────────────────────────────────────────────────────────
# Output dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FeatureSet:
    session_id: str
    page: str
    batch_t: float
    features: dict[str, float]      # named features
    vector: list[float]             # ordered vector for the model


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _safe(val: float) -> float:
    """Replace NaN/inf with 0.0 to avoid crashing the model."""
    if val is None or math.isnan(val) or math.isinf(val):
        return 0.0
    return round(float(val), 6)


# ─────────────────────────────────────────────────────────────────────────────
# Heuristic rules — immediate score without a trained model
# ─────────────────────────────────────────────────────────────────────────────

BOT_RULES = [
    # (feature, operator, threshold, weight, description)
    ("entropy_direction",      "<",  0.5,   3.0, "Linear trajectory — very low directional entropy"),
    ("entropy_speed",          "<",  0.3,   2.5, "Constant speed — very low speed entropy"),
    ("constant_speed_ratio",   ">",  0.8,   2.5, "80%+ of segments at near-constant speed"),
    ("path_efficiency",        ">",  0.95,  2.0, "Perfectly straight-line movement"),
    ("std_turning_angle",      "<",  0.05,  2.0, "Turning angles too regular"),
    ("interclick_min",         "<",  0.05,  2.0, "Click in under 50ms"),
    ("interclick_std",         "<",  0.01,  1.5, "Identical inter-click delays"),
    ("field_min_duration",     "<",  0.1,   3.0, "Field filled in under 100ms"),
    ("click_move_ratio",       ">",  0.3,   2.0, "Too many clicks relative to movements"),
    ("session_duration",       "<",  3.0,   2.5, "Session shorter than 3 seconds"),
    ("scroll_depth_max",       "<",  0.05,  1.5, "No scroll despite clicks"),
    ("teleport_count",         ">",  5.0,   1.5, "Abnormally fast movements"),
    ("mean_acceleration",      "<",  0.001, 1.5, "Near-zero acceleration — linear interpolation"),
]


class FeatureService:
    """
    Extracts normalized feature vectors from mouse behavior batches.
    Provides both standard feature extraction and heuristic scoring.
    """

    def __init__(self):
        """Initialize feature service."""
        self.feature_columns = FEATURE_COLUMNS
        self.bot_rules = BOT_RULES

    def extract(self, batch: MouseBehaviorBatch) -> FeatureSet:
        """
        Extract features from a validated behavior batch.

        Args:
            batch: Validated MouseBehaviorBatch

        Returns:
            FeatureSet with named features and ordered vector
        """
        m = batch.movement
        cl = batch.clicks
        sc = batch.scroll
        h = batch.heuristics
        f = batch.form
        n = batch.navigation

        # --- A — Movement ---
        click_move_ratio = (
            cl.total_click_events / m.total_move_events
            if m.total_move_events > 0
            else float(cl.total_click_events)  # clicks with no movement = strong bot signal
        )

        scroll_click_ratio = (
            sc.scroll_depth_max / cl.total_click_events
            if cl.total_click_events > 0
            else sc.scroll_depth_max
        )

        features = {
            # A — Movement
            "entropy_direction": _safe(h.entropy_direction),
            "entropy_speed": _safe(h.entropy_speed),
            "speed_variance": _safe(m.std_speed_rel**2),
            "max_speed": _safe(m.max_speed_rel),
            "mean_acceleration": _safe(m.mean_acceleration_rel),
            "path_efficiency": _safe(h.linear_movement_ratio),
            "direction_changes": float(m.direction_changes_count),
            "mean_turning_angle": _safe(m.mean_turning_angle_rad),
            "std_turning_angle": _safe(m.std_turning_angle_rad),
            "constant_speed_ratio": _safe(h.constant_speed_ratio),
            "teleport_count": float(h.teleport_event_count),
            # B — Clicks
            "click_move_ratio": _safe(click_move_ratio),
            "interclick_min": _safe(cl.min_click_interval_sec),
            "interclick_std": _safe(cl.std_click_interval_sec),
            "click_hold_mean": _safe(cl.mean_click_hold_sec),
            "rapid_burst_count": float(cl.rapid_click_burst_count),
            "identical_interval_ratio": _safe(cl.identical_interval_ratio),
            # C — Forms
            "field_min_duration": _safe(f.field_min_duration_sec),
            "field_avg_duration": _safe(f.field_avg_duration_sec),
            "fields_filled": float(f.fields_filled),
            # D — Scroll
            "scroll_depth_max": _safe(sc.scroll_depth_max),
            "scroll_event_rate": _safe(sc.scroll_event_rate_hz),
            "scroll_direction_changes": float(sc.scroll_direction_changes),
            # E — Session
            "session_duration": _safe(n.session_duration_sec),
            "pages_visited": float(len(n.pages_visited)),
            "revisit_rate": _safe(n.revisit_rate),
            "scroll_click_ratio": _safe(scroll_click_ratio),
        }

        vector = [features[col] for col in FEATURE_COLUMNS]

        return FeatureSet(
            session_id=batch.session_id,
            page=batch.page,
            batch_t=batch.batch_t,
            features=features,
            vector=vector,
        )

    def to_numpy(self, feature_set: FeatureSet) -> np.ndarray:
        """
        Convert feature set to 2D numpy array for scikit-learn.

        Args:
            feature_set: FeatureSet to convert

        Returns:
            np.ndarray: Shape (1, N_FEATURES)
        """
        return np.array(feature_set.vector, dtype=float).reshape(1, -1)

    def heuristic_score(
        self, feature_set: FeatureSet
    ) -> tuple[float, list[str]]:
        """
        Rule-based bot score without a trained model.

        Args:
            feature_set: FeatureSet to score

        Returns:
            tuple: (score 0.0–1.0, list of triggered rules)
        """
        f = feature_set.features
        triggered = []
        weighted_sum = 0.0
        total_weight = sum(r[3] for r in self.bot_rules)

        for col, op, threshold, weight, reason in self.bot_rules:
            val = f.get(col, 0.0)
            hit = (op == "<" and val < threshold) or (
                op == ">" and val > threshold
            )
            if hit:
                weighted_sum += weight
                triggered.append(f"[{col} {op} {threshold}] {reason}")

        score = weighted_sum / total_weight
        return round(min(1.0, score), 4), triggered


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton for backward compatibility
# ─────────────────────────────────────────────────────────────────────────────

_default_service: FeatureService | None = None


def get_service() -> FeatureService:
    """Get or create the default feature service singleton."""
    global _default_service
    if _default_service is None:
        logger.debug("Initializing default FeatureService instance")
        _default_service = FeatureService()
    return _default_service


# ─────────────────────────────────────────────────────────────────────────────
# Legacy module-level functions for backward compatibility
# ─────────────────────────────────────────────────────────────────────────────


def extract(batch: MouseBehaviorBatch) -> FeatureSet:
    """Backward compatible extract function. Uses default service singleton."""
    return get_service().extract(batch)


def to_numpy(feature_set: FeatureSet) -> np.ndarray:
    """Backward compatible to_numpy function. Uses default service singleton."""
    return get_service().to_numpy(feature_set)


def heuristic_score(feature_set: FeatureSet) -> tuple[float, list[str]]:
    """Backward compatible heuristic_score function. Uses default service singleton."""
    return get_service().heuristic_score(feature_set)
