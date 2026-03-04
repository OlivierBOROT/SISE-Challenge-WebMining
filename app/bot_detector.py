"""
Bot detection via Isolation Forest on mouse-movement features.

The model is pre-trained on synthetic "human-like" feature distributions
so that it can flag anomalous (bot-like) behaviour from the very first
request.

The feature vector is computed client-side by mouseTracker.js and
includes ~40 dimensions covering speed, acceleration, jerk, geometry,
timing regularity, jitter, scroll, click patterns, keyboard activity,
coordinate integrity, and session behaviour.

Scores closer to -1 → anomaly (bot), closer to +1 → normal (human).
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

_RNG = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# Feature specification
# ---------------------------------------------------------------------------
FEATURE_NAMES: list[str] = [
    # Timing regularity  (bots: very low CV & entropy)
    "dt_mean",
    "dt_std",
    "dt_cv",
    "dt_min",
    "dt_max",
    "dt_median",
    "dt_entropy",
    # Speed
    "speed_avg",
    "speed_std",
    "speed_max",
    "speed_min",
    "speed_median",
    # Acceleration
    "accel_avg",
    "accel_std",
    "accel_max",
    # Jerk  (3rd derivative — bots often zero)
    "jerk_avg",
    "jerk_std",
    "jerk_max",
    # Angular velocity
    "ang_vel_avg",
    "ang_vel_std",
    # Trajectory geometry
    "curvature_avg",
    "curvature_std",
    "angle_avg",
    "angle_std",
    "dir_changes",
    "straightness",
    "sinuosity",
    # Micro-jitter  (humans ≈ 8-12 Hz tremor)
    "jitter",
    "jitter_mean",
    "jitter_hz",
    "jitter_score",
    # Coordinate integrity  (bots: 100 % integer coords, no movementX)
    "int_coord_ratio",
    "has_movement_ratio",
    "movement_drift_x",
    "movement_drift_y",
    # Scroll
    "scroll_count",
    "scroll_dy_total",
    "scroll_dt_cv",
    # Click patterns
    "total_clicks",
    "clicks_per_sec",
    "click_dt_cv",
    "click_dt_mean",
    "move_to_click_delay_avg",
    # Idle / pauses
    "idle_ratio",
    "pause_count",
    # Activity
    "events_per_sec",
    # Keyboard
    "has_keyboard_activity",
    "keys_per_sec",
    # Tab visibility
    "tab_blur_count",
    "tab_hidden_ratio",
    # Entry behaviour
    "first_move_delay",
    "first_click_delay",
]

N_FEATURES = len(FEATURE_NAMES)


# ---------------------------------------------------------------------------
# Synthetic human-like training data
# ---------------------------------------------------------------------------
def _generate_human_samples(n: int = 600) -> np.ndarray:
    """Return (n, N_FEATURES) array of plausible human feature vectors."""
    r = _RNG
    cols: list[np.ndarray] = []

    # Timing
    dt_mean = r.normal(12, 4, n).clip(4, 40)
    dt_std = r.lognormal(1.5, 0.6, n).clip(1, 30)
    dt_cv = dt_std / np.maximum(dt_mean, 0.1)
    dt_min = r.uniform(1, 6, n)
    dt_max = r.lognormal(4.0, 0.8, n).clip(20, 500)
    dt_med = dt_mean + r.normal(0, 2, n)
    dt_ent = r.uniform(2.5, 4.2, n)
    cols += [dt_mean, dt_std, dt_cv, dt_min, dt_max, dt_med, dt_ent]

    # Speed
    cols.append(r.lognormal(6.0, 0.6, n))  # speed_avg
    cols.append(r.lognormal(5.5, 0.7, n))  # speed_std
    cols.append(r.lognormal(7.0, 0.5, n))  # speed_max
    cols.append(r.uniform(0, 50, n))  # speed_min
    cols.append(r.lognormal(5.8, 0.6, n))  # speed_median

    # Acceleration
    cols.append(r.lognormal(6.5, 0.8, n))  # accel_avg
    cols.append(r.lognormal(6.0, 0.7, n))  # accel_std
    cols.append(r.lognormal(8.0, 0.7, n))  # accel_max

    # Jerk
    cols.append(r.lognormal(8.0, 1.0, n))  # jerk_avg
    cols.append(r.lognormal(8.5, 1.0, n))  # jerk_std
    cols.append(r.lognormal(10.0, 1.0, n))  # jerk_max

    # Angular velocity
    cols.append(r.lognormal(6.0, 0.8, n))  # ang_vel_avg
    cols.append(r.lognormal(6.5, 0.9, n))  # ang_vel_std

    # Geometry
    cols.append(r.exponential(0.05, n) + 0.001)  # curvature_avg
    cols.append(r.exponential(0.04, n) + 0.001)  # curvature_std
    cols.append(r.uniform(5, 60, n))  # angle_avg
    cols.append(r.uniform(5, 40, n))  # angle_std
    cols.append(r.poisson(8, n).astype(float))  # dir_changes
    cols.append(r.beta(2, 5, n) * 0.7 + 0.15)  # straightness
    cols.append(r.lognormal(0.5, 0.4, n))  # sinuosity

    # Jitter
    cols.append(r.exponential(2.0, n) + 0.3)  # jitter (σ)
    cols.append(r.exponential(1.5, n) + 0.3)  # jitter_mean
    cols.append(r.uniform(20, 120, n))  # jitter_hz
    cols.append(r.exponential(0.5, n) + 0.01)  # jitter_score

    # Coordinate integrity — humans: mostly integer but some fractional
    cols.append(r.beta(8, 2, n))  # int_coord_ratio 0.7-1.0
    cols.append(r.beta(8, 1, n))  # has_movement_ratio  ~0.9+
    cols.append(r.exponential(5, n))  # movement_drift_x  small
    cols.append(r.exponential(5, n))  # movement_drift_y  small

    # Scroll
    cols.append(r.poisson(15, n).astype(float))  # scroll_count
    cols.append(r.lognormal(6, 1, n))  # scroll_dy_total
    cols.append(r.uniform(0.3, 1.5, n))  # scroll_dt_cv

    # Clicks
    cols.append(r.poisson(5, n).astype(float))  # total_clicks
    cols.append(r.uniform(0.05, 0.8, n))  # clicks_per_sec
    cols.append(r.uniform(0.3, 2.0, n))  # click_dt_cv
    cols.append(r.lognormal(7, 0.8, n))  # click_dt_mean  ms
    cols.append(r.lognormal(3.5, 0.8, n))  # move_to_click_delay_avg ms

    # Idle / pauses
    cols.append(r.beta(1.5, 6, n))  # idle_ratio 0-0.3
    cols.append(r.poisson(3, n).astype(float))  # pause_count

    # Activity
    cols.append(r.uniform(30, 144, n))  # events_per_sec

    # Keyboard
    cols.append(r.binomial(1, 0.4, n).astype(float))  # has_keyboard_activity
    cols.append(r.exponential(0.3, n))  # keys_per_sec

    # Tab visibility
    cols.append(r.poisson(1, n).astype(float))  # tab_blur_count
    cols.append(r.beta(1, 10, n))  # tab_hidden_ratio

    # Entry behaviour
    cols.append(r.lognormal(7, 1, n).clip(200, 30000))  # first_move_delay ms
    cols.append(r.lognormal(8, 1.2, n).clip(500, 60000))  # first_click_delay ms

    assert len(cols) == N_FEATURES, f"Expected {N_FEATURES} cols, got {len(cols)}"
    return np.column_stack(cols)


# ---------------------------------------------------------------------------
# Model singleton
# ---------------------------------------------------------------------------
_model: IsolationForest | None = None


def _get_model() -> IsolationForest:
    global _model
    if _model is None:
        X_train = _generate_human_samples(600)
        _model = IsolationForest(
            n_estimators=200,
            contamination=0.08,
            random_state=42,
            n_jobs=-1,
        )
        _model.fit(X_train)
    return _model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def detect(features: dict[str, float]) -> dict:
    """
    Run bot detection on a single feature vector.

    Parameters
    ----------
    features : dict
        Keys should match FEATURE_NAMES.  Missing keys default to 0.

    Returns
    -------
    dict with:
        label       : "human" | "bot"
        score       : float   (decision_function; < 0 → anomaly)
        anomaly     : int     (-1 = bot, 1 = human)
        confidence  : float   (0–1)
        features_used : list[str]
    """
    model = _get_model()
    x = np.array([[features.get(f, 0.0) for f in FEATURE_NAMES]])

    score = float(model.decision_function(x)[0])
    prediction = int(model.predict(x)[0])

    confidence = min(1.0, abs(score) / 0.15)

    return {
        "label": "human" if prediction == 1 else "bot",
        "score": round(score, 4),
        "anomaly": prediction,
        "confidence": round(confidence, 3),
        "features_used": FEATURE_NAMES,
    }
