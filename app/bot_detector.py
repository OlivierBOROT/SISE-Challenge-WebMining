"""
Bot detection via Isolation Forest sur les features de comportement souris.

Le modèle est pré-entraîné sur des données synthétiques « humain-like »
pour pouvoir classifier dès la première requête.

Le vecteur de features (53 dimensions) est calculé côté client par
mouseTracker.js puis aplati et envoyé ici via /ajax/detect.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

_RNG = np.random.default_rng(42)

# ──────────────────────────────────────────────
# Spécification des features (ordre = colonnes du modèle)
# ──────────────────────────────────────────────
FEATURE_NAMES: list[str] = [
    # Session
    "elapsed_since_session_start_sec",
    "capture_duration_sec",
    # Movement
    "total_move_events",
    "move_event_rate_hz",
    "mean_delta_time_sec",
    "std_delta_time_sec",
    "min_delta_time_sec",
    "max_delta_time_sec",
    "total_distance_rel",
    "net_displacement_rel",
    "path_efficiency_ratio",
    "mean_speed_rel",
    "std_speed_rel",
    "max_speed_rel",
    "min_speed_rel",
    "mean_acceleration_rel",
    "std_acceleration_rel",
    "max_acceleration_rel",
    "mean_turning_angle_rad",
    "std_turning_angle_rad",
    "direction_changes_count",
    "micro_movements_ratio",
    "zero_delta_ratio",
    "jitter_index",
    # Clicks
    "total_click_events",
    "left_click_count",
    "right_click_count",
    "middle_click_count",
    "double_click_count",
    "mean_click_interval_sec",
    "std_click_interval_sec",
    "min_click_interval_sec",
    "max_click_interval_sec",
    "mean_click_hold_sec",
    "std_click_hold_sec",
    "max_click_hold_sec",
    "rapid_click_burst_count",
    "identical_interval_ratio",
    # Scroll
    "total_scroll_events",
    "scroll_event_rate_hz",
    "mean_scroll_delta_rel",
    "std_scroll_delta_rel",
    "max_scroll_delta_rel",
    "scroll_direction_changes",
    "continuous_scroll_sequences",
    "mean_scroll_interval_sec",
    # Heuristics
    "constant_speed_ratio",
    "linear_movement_ratio",
    "perfect_straight_lines_count",
    "teleport_event_count",
    "event_uniformity_score",
    "entropy_direction",
    "entropy_speed",
]

N_FEATURES = len(FEATURE_NAMES)  # 53


# ──────────────────────────────────────────────
# Données synthétiques humaines pour l'entraînement
# ──────────────────────────────────────────────
def _generate_human_samples(n: int = 600) -> np.ndarray:
    """Génère (n, N_FEATURES) vecteurs humains plausibles."""
    r = _RNG
    cols: list[np.ndarray] = []

    # Session
    elapsed = r.uniform(5, 120, n)
    cols.append(elapsed)  # elapsed_since_session_start_sec
    cols.append(elapsed - r.uniform(0, 2, n).clip(0, None))  # capture_duration_sec

    # Movement — timing
    cols.append(elapsed * r.uniform(40, 100, n))  # total_move_events
    cols.append(r.uniform(40, 120, n))  # move_event_rate_hz
    cols.append(r.uniform(0.008, 0.03, n))  # mean_delta_time_sec
    cols.append(r.uniform(0.002, 0.02, n))  # std_delta_time_sec
    cols.append(r.uniform(0.001, 0.008, n))  # min_delta_time_sec
    cols.append(r.uniform(0.05, 1.0, n))  # max_delta_time_sec

    # Movement — distance
    cols.append(r.lognormal(1.5, 0.8, n))  # total_distance_rel
    cols.append(r.lognormal(0.0, 0.8, n))  # net_displacement_rel
    cols.append(r.beta(2, 5, n) * 0.5 + 0.01)  # path_efficiency_ratio

    # Movement — speed
    cols.append(r.lognormal(-1.0, 0.6, n))  # mean_speed_rel
    cols.append(r.lognormal(-1.5, 0.6, n))  # std_speed_rel
    cols.append(r.lognormal(0.0, 0.6, n))  # max_speed_rel
    cols.append(r.exponential(0.01, n))  # min_speed_rel

    # Movement — acceleration
    cols.append(r.lognormal(1.0, 0.8, n))  # mean_acceleration_rel
    cols.append(r.lognormal(2.0, 0.9, n))  # std_acceleration_rel
    cols.append(r.lognormal(3.0, 0.8, n))  # max_acceleration_rel

    # Movement — angles
    cols.append(r.normal(0, 0.05, n))  # mean_turning_angle_rad
    cols.append(r.uniform(0.3, 1.5, n))  # std_turning_angle_rad
    cols.append(r.poisson(20, n).astype(float))  # direction_changes_count

    # Movement — micro-movements
    cols.append(r.beta(2, 6, n))  # micro_movements_ratio
    cols.append(r.beta(1, 20, n))  # zero_delta_ratio
    cols.append(r.uniform(0.5, 3.0, n))  # jitter_index

    # Clicks
    cols.append(r.poisson(5, n).astype(float))  # total_click_events
    cols.append(r.poisson(4, n).astype(float))  # left_click_count
    cols.append(r.poisson(1, n).astype(float))  # right_click_count
    cols.append(r.poisson(0.2, n).astype(float))  # middle_click_count
    cols.append(r.poisson(0.5, n).astype(float))  # double_click_count
    cols.append(r.lognormal(0.5, 0.8, n))  # mean_click_interval_sec
    cols.append(r.lognormal(0.0, 0.8, n))  # std_click_interval_sec
    cols.append(r.uniform(0.1, 1.0, n))  # min_click_interval_sec
    cols.append(r.lognormal(1.5, 0.8, n))  # max_click_interval_sec
    cols.append(r.uniform(0.05, 0.3, n))  # mean_click_hold_sec
    cols.append(r.uniform(0.01, 0.15, n))  # std_click_hold_sec
    cols.append(r.uniform(0.1, 0.8, n))  # max_click_hold_sec
    cols.append(r.poisson(0.3, n).astype(float))  # rapid_click_burst_count
    cols.append(r.beta(1, 10, n))  # identical_interval_ratio

    # Scroll
    cols.append(r.poisson(10, n).astype(float))  # total_scroll_events
    cols.append(r.uniform(0.1, 3.0, n))  # scroll_event_rate_hz
    cols.append(r.exponential(0.02, n))  # mean_scroll_delta_rel
    cols.append(r.exponential(0.01, n))  # std_scroll_delta_rel
    cols.append(r.exponential(0.05, n))  # max_scroll_delta_rel
    cols.append(r.poisson(2, n).astype(float))  # scroll_direction_changes
    cols.append(r.poisson(3, n).astype(float))  # continuous_scroll_sequences
    cols.append(r.uniform(0.1, 2.0, n))  # mean_scroll_interval_sec

    # Heuristics
    cols.append(r.beta(2, 8, n))  # constant_speed_ratio
    cols.append(r.beta(2, 5, n))  # linear_movement_ratio
    cols.append(r.poisson(1, n).astype(float))  # perfect_straight_lines_count
    cols.append(r.poisson(0.1, n).astype(float))  # teleport_event_count
    cols.append(r.beta(2, 5, n))  # event_uniformity_score
    cols.append(r.uniform(1.5, 3.0, n))  # entropy_direction
    cols.append(r.uniform(1.0, 3.3, n))  # entropy_speed

    assert len(cols) == N_FEATURES, f"Expected {N_FEATURES} cols, got {len(cols)}"
    return np.column_stack(cols)


# ──────────────────────────────────────────────
# Singleton du modèle
# ──────────────────────────────────────────────
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


# ──────────────────────────────────────────────
# API publique
# ──────────────────────────────────────────────
def detect(features: dict[str, float]) -> dict:
    """
    Détection bot sur un vecteur de features.

    Parameters
    ----------
    features : dict
        Clés correspondant à FEATURE_NAMES. Les clés manquantes → 0.

    Returns
    -------
    dict avec label, score, anomaly, confidence, features_used
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
