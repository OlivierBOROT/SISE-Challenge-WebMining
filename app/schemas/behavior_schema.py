"""
Schema definitions for mouse behavior features used in bot detection.
"""

from pydantic import BaseModel


class MovementMetrics(BaseModel):
    """Metrics related to mouse movement events."""

    total_move_events: int
    move_event_rate_hz: float  # events/sec

    mean_delta_time_sec: float  # time delta between movements in seconds
    std_delta_time_sec: float
    min_delta_time_sec: float
    max_delta_time_sec: float

    total_distance_rel: float  # distance / viewport diagonal
    net_displacement_rel: float  # net displacement / viewport diagonal
    path_efficiency_ratio: float

    mean_speed_rel: float  # speed normalized by viewport diagonal and deltaT
    std_speed_rel: float
    max_speed_rel: float
    min_speed_rel: float

    mean_acceleration_rel: (
        float  # acceleration normalized by viewport diagonal and deltaT^2
    )
    std_acceleration_rel: float
    max_acceleration_rel: float

    mean_turning_angle_rad: float
    std_turning_angle_rad: float
    direction_changes_count: int

    micro_movements_ratio: float
    zero_delta_ratio: float
    jitter_index: float


class ClickMetrics(BaseModel):
    """Metrics related to click events."""

    total_click_events: int

    left_click_count: int
    right_click_count: int
    middle_click_count: int
    double_click_count: int

    mean_click_interval_sec: float
    std_click_interval_sec: float
    min_click_interval_sec: float
    max_click_interval_sec: float

    mean_click_hold_sec: float
    std_click_hold_sec: float
    max_click_hold_sec: float

    rapid_click_burst_count: int
    identical_interval_ratio: float


class ScrollMetrics(BaseModel):
    """Metrics related to scroll events."""

    total_scroll_events: int
    scroll_event_rate_hz: float

    mean_scroll_delta_rel: float  # scroll delta / viewport height
    std_scroll_delta_rel: float
    max_scroll_delta_rel: float

    scroll_direction_changes: int
    continuous_scroll_sequences: int
    mean_scroll_interval_sec: float

    scroll_depth_max: float = 0.0  # max scroll position reached (0.0 - 1.0)


class HeuristicMetrics(BaseModel):
    """Hand-crafted heuristics that may indicate bot-like behavior."""

    constant_speed_ratio: float
    linear_movement_ratio: float
    perfect_straight_lines_count: int
    teleport_event_count: int
    event_uniformity_score: float
    entropy_direction: float
    entropy_speed: float


class FormMetrics(BaseModel):
    """Metrics related to form interaction events."""

    fields_filled: int = 0
    field_avg_duration_sec: float = 0.0
    field_min_duration_sec: float = 0.0  # most revealing for bots (bot ≈ 0ms)
    field_order: list[str] = []


class NavigationMetrics(BaseModel):
    """Metrics related to page navigation within the session."""

    pages_visited: list[str] = []
    unique_pages: int = 0
    revisit_rate: float = 0.0
    session_duration_sec: float = 0.0


class MouseBehaviorBatch(BaseModel):
    """Full batch of mouse behavior data sent from the JS frontend every 10s."""

    # Metadata
    session_id: str
    page: str
    batch_t: float  # ms since session start

    # Sub-modules
    movement: MovementMetrics
    clicks: ClickMetrics
    scroll: ScrollMetrics
    heuristics: HeuristicMetrics
    form: FormMetrics = FormMetrics()
    navigation: NavigationMetrics = NavigationMetrics()
