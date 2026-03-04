from pydantic import BaseModel


class MovementMetrics(BaseModel):
    total_move_events: int
    move_event_rate_hz: float  # events/sec

    mean_delta_time_sec: float  # delta entre mouvements en secondes
    std_delta_time_sec: float
    min_delta_time_sec: float
    max_delta_time_sec: float

    total_distance_rel: float  # distance / diagonal viewport
    net_displacement_rel: float  # net / diagonal viewport
    path_efficiency_ratio: float

    mean_speed_rel: float  # vitesse normalisée par diag et deltaT
    std_speed_rel: float
    max_speed_rel: float
    min_speed_rel: float

    mean_acceleration_rel: float  # accel normalisée par diag et deltaT^2
    std_acceleration_rel: float
    max_acceleration_rel: float

    mean_turning_angle_rad: float
    std_turning_angle_rad: float
    direction_changes_count: int

    micro_movements_ratio: float
    zero_delta_ratio: float
    jitter_index: float


class ClickMetrics(BaseModel):
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
    total_scroll_events: int
    scroll_event_rate_hz: float

    mean_scroll_delta_rel: float  # delta / viewport height
    std_scroll_delta_rel: float
    max_scroll_delta_rel: float

    scroll_direction_changes: int
    continuous_scroll_sequences: int
    mean_scroll_interval_sec: float


class HeuristicMetrics(BaseModel):
    constant_speed_ratio: float
    linear_movement_ratio: float
    perfect_straight_lines_count: int
    teleport_event_count: int
    event_uniformity_score: float
    entropy_direction: float
    entropy_speed: float


class MouseBehaviorFeatures(BaseModel):
    session_start_ts: int
    elapsed_since_session_start_sec: float
    capture_duration_sec: float
    total_events: int

    movement: MovementMetrics
    clicks: ClickMetrics
    scroll: ScrollMetrics
    heuristics: HeuristicMetrics
