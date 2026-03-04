"""
Feature Service
Receives a validated MouseBehaviorBatch and produces a normalized feature
vector ready to be passed to the ML model.
"""

import math
import numpy as np
from dataclasses import dataclass
from app.schemas import MouseBehaviorBatch


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
# Extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract(batch: MouseBehaviorBatch) -> FeatureSet:
    """
    Main entry point.
    Receives a validated batch and returns a FeatureSet with named features + ordered vector.
    """
    m  = batch.movement
    cl = batch.clicks
    sc = batch.scroll
    h  = batch.heuristics
    f  = batch.form
    n  = batch.navigation

    # --- A — Movement ---
    click_move_ratio = (
        cl.total_click_events / m.total_move_events
        if m.total_move_events > 0
        else float(cl.total_click_events)   # clicks with no movement = strong bot signal
    )

    scroll_click_ratio = (
        sc.scroll_depth_max / cl.total_click_events
        if cl.total_click_events > 0
        else sc.scroll_depth_max
    )

    features = {
        # A — Movement
        "entropy_direction":       _safe(h.entropy_direction),
        "entropy_speed":           _safe(h.entropy_speed),
        "speed_variance":          _safe(m.std_speed_rel ** 2),
        "max_speed":               _safe(m.max_speed_rel),
        "mean_acceleration":       _safe(m.mean_acceleration_rel),
        "path_efficiency":         _safe(h.linear_movement_ratio),
        "direction_changes":       float(m.direction_changes_count),
        "mean_turning_angle":      _safe(m.mean_turning_angle_rad),
        "std_turning_angle":       _safe(m.std_turning_angle_rad),
        "constant_speed_ratio":    _safe(h.constant_speed_ratio),
        "teleport_count":          float(h.teleport_event_count),

        # B — Clicks
        "click_move_ratio":        _safe(click_move_ratio),
        "interclick_min":          _safe(cl.min_click_interval_sec),
        "interclick_std":          _safe(cl.std_click_interval_sec),
        "click_hold_mean":         _safe(cl.mean_click_hold_sec),
        "rapid_burst_count":       float(cl.rapid_click_burst_count),
        "identical_interval_ratio": _safe(cl.identical_interval_ratio),

        # C — Forms
        "field_min_duration":      _safe(f.field_min_duration_sec),
        "field_avg_duration":      _safe(f.field_avg_duration_sec),
        "fields_filled":           float(f.fields_filled),

        # D — Scroll
        "scroll_depth_max":        _safe(sc.scroll_depth_max),
        "scroll_event_rate":       _safe(sc.scroll_event_rate_hz),
        "scroll_direction_changes": float(sc.scroll_direction_changes),

        # E — Session
        "session_duration":        _safe(n.session_duration_sec),
        "pages_visited":           float(len(n.pages_visited)),
        "revisit_rate":            _safe(n.revisit_rate),
        "scroll_click_ratio":      _safe(scroll_click_ratio),
    }

    vector = [features[col] for col in FEATURE_COLUMNS]

    return FeatureSet(
        session_id=batch.session_id,
        page=batch.page,
        batch_t=batch.batch_t,
        features=features,
        vector=vector,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(val: float) -> float:
    """Replace NaN/inf with 0.0 to avoid crashing the model."""
    if val is None or math.isnan(val) or math.isinf(val):
        return 0.0
    return round(float(val), 6)


def to_numpy(feature_set: FeatureSet) -> np.ndarray:
    """Return the feature vector as a 2D numpy array for scikit-learn."""
    return np.array(feature_set.vector, dtype=float).reshape(1, -1)


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


def heuristic_score(feature_set: FeatureSet) -> tuple[float, list[str]]:
    """
    Rule-based score — works without a trained model.
    Returns (score 0.0–1.0, list of triggered rules).
    """
    f = feature_set.features
    triggered = []
    weighted_sum = 0.0
    total_weight = sum(r[3] for r in BOT_RULES)

    for col, op, threshold, weight, reason in BOT_RULES:
        val = f.get(col, 0.0)
        hit = (op == "<" and val < threshold) or (op == ">" and val > threshold)
        if hit:
            weighted_sum += weight
            triggered.append(f"[{col} {op} {threshold}] {reason}")

    score = weighted_sum / total_weight
    return round(min(1.0, score), 4), triggered


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from app.schemas import (
        MouseBehaviorBatch, MovementMetrics, ClickMetrics,
        ScrollMetrics, HeuristicMetrics, FormMetrics, NavigationMetrics
    )

    def make_batch(label: str, **overrides) -> MouseBehaviorBatch:
        """Build a test batch with default human or bot values."""
        is_bot = label == "bot"
        return MouseBehaviorBatch(
            session_id=f"test-{label}-001",
            page="/checkout",
            batch_t=1200.0 if is_bot else 10000.0,
            movement=MovementMetrics(
                total_move_events=4 if is_bot else 80,
                move_event_rate_hz=0.4 if is_bot else 8.0,
                mean_delta_time_sec=0.1,
                std_delta_time_sec=0.0 if is_bot else 0.05,
                min_delta_time_sec=0.1,
                max_delta_time_sec=0.1 if is_bot else 0.8,
                total_distance_rel=0.5,
                net_displacement_rel=0.5 if is_bot else 0.2,  # ratio → 1.0 for bot
                path_efficiency_ratio=0.99 if is_bot else 0.45,
                mean_speed_rel=0.02 if is_bot else 0.015,
                std_speed_rel=0.0 if is_bot else 0.008,       # zero variance for bot
                max_speed_rel=0.02 if is_bot else 0.04,
                min_speed_rel=0.02 if is_bot else 0.002,
                mean_acceleration_rel=0.0 if is_bot else 0.003,
                std_acceleration_rel=0.0 if is_bot else 0.002,
                max_acceleration_rel=0.0 if is_bot else 0.01,
                mean_turning_angle_rad=0.0 if is_bot else 0.8,
                std_turning_angle_rad=0.0 if is_bot else 0.4,
                direction_changes_count=0 if is_bot else 25,
                micro_movements_ratio=0.0,
                zero_delta_ratio=0.0,
                jitter_index=0.0,
            ),
            clicks=ClickMetrics(
                total_click_events=3,
                left_click_count=3,
                right_click_count=0,
                middle_click_count=0,
                double_click_count=0,
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
                teleport_event_count=0,
                event_uniformity_score=0.0,
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

    print("=" * 60)
    for label in ["human", "bot"]:
        batch = make_batch(label)
        fs = extract(batch)
        score, triggered = heuristic_score(fs)

        print(f"\n{'🟢 HUMAN' if label == 'human' else '🔴 BOT'} — heuristic score: {score:.2f}")
        print(f"{'─'*40}")
        print(f"{'Feature':<30} {'Value':>10}")
        print(f"{'─'*40}")
        for col in FEATURE_COLUMNS:
            print(f"  {col:<28} {fs.features[col]:>10.4f}")

        if triggered:
            print("\n  ⚠️  Triggered rules:")
            for r in triggered:
                print(f"     → {r}")

    print("\n" + "="*60)
    print("Bot vector:", to_numpy(extract(make_batch('bot')))[0].tolist())
