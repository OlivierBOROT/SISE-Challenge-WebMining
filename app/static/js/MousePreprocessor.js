// mouse_preprocess.js
class MousePreprocessor {
  constructor() {
    // --- Raw event buffers ---
    this.moves = [];       // {x, y, timestamp}
    this.clicks = [];      // {button, downTs, upTs}
    this.scrolls = [];     // {deltaY, timestamp}
    
    // --- Session info ---
    this.sessionStart = Date.now();

    // Bind events
    window.addEventListener("mousemove", this.onMouseMove.bind(this));
    window.addEventListener("mousedown", this.onMouseDown.bind(this));
    window.addEventListener("mouseup", this.onMouseUp.bind(this));
    window.addEventListener("wheel", this.onWheel.bind(this));
  }

  // ------------------ Event handlers ------------------
  onMouseMove(e) {
    this.moves.push({
      x: e.clientX,
      y: e.clientY,
      ts: Date.now()
    });
  }

  onMouseDown(e) {
    this.clicks.push({ button: e.button, downTs: Date.now(), upTs: null });
  }

  onMouseUp(e) {
    const lastClick = this.clicks.slice().reverse().find(c => c.button === e.button && c.upTs === null);
    if (lastClick) lastClick.upTs = Date.now();
  }

  onWheel(e) {
    this.scrolls.push({ deltaY: e.deltaY, ts: Date.now() });
  }

  // ------------------ Utilities ------------------
  distance(a, b) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    return Math.sqrt(dx*dx + dy*dy);
  }

  // Normalized distance by viewport diagonal
  normalizedDistance(a, b) {
    const diag = Math.sqrt(window.innerWidth**2 + window.innerHeight**2);
    return this.distance(a, b) / diag;
  }

  // ------------------ Feature computation ------------------
  computeFeatures() {
    const now = Date.now();
    const elapsedSec = (now - this.sessionStart) / 1000;
    const captureDurationSec = elapsedSec; // for first window; can adjust if using sliding window

    // --- Movement metrics ---
    const moveEvents = this.moves.length;
    const moveEventRateHz = moveEvents / captureDurationSec;

    let totalDistance = 0, netDistance = 0;
    let meanSpeed = 0, stdSpeed = 0;
    const speeds = [];
    const angles = [];
    let directionChanges = 0;

    for (let i = 1; i < this.moves.length; i++) {
      const prev = this.moves[i-1];
      const curr = this.moves[i];
      const dtSec = (curr.ts - prev.ts) / 1000;
      const d = this.normalizedDistance(prev, curr);
      totalDistance += d;
      speeds.push(d / dtSec);

      if (i === 1) {
        angles.push(0);
      } else {
        const prevVec = {
          x: prev.x - this.moves[i-2].x,
          y: prev.y - this.moves[i-2].y
        };
        const currVec = {
          x: curr.x - prev.x,
          y: curr.y - prev.y
        };
        const dot = prevVec.x*currVec.x + prevVec.y*currVec.y;
        const magPrev = Math.sqrt(prevVec.x**2 + prevVec.y**2);
        const magCurr = Math.sqrt(currVec.x**2 + currVec.y**2);
        const cosTheta = Math.max(-1, Math.min(1, dot / (magPrev*magCurr + 1e-10)));
        const angle = Math.acos(cosTheta);
        angles.push(angle);
        if (angle > 0.1) directionChanges += 1; // threshold 0.1 rad
      }
    }

    if (this.moves.length >= 2) {
      const first = this.moves[0];
      const last = this.moves[this.moves.length-1];
      netDistance = this.normalizedDistance(first, last);
    }

    const meanSpeedVal = speeds.reduce((a,b)=>a+b,0)/speeds.length || 0;
    stdSpeed = Math.sqrt(speeds.reduce((a,b)=>a + (b-meanSpeedVal)**2,0)/speeds.length) || 0;
    const meanAngle = angles.reduce((a,b)=>a+b,0)/angles.length || 0;
    const stdAngle = Math.sqrt(angles.reduce((a,b)=>a + (b-meanAngle)**2,0)/angles.length) || 0;

    // --- Click metrics ---
    const totalClicks = this.clicks.length;
    const leftClicks = this.clicks.filter(c=>c.button===0).length;
    const rightClicks = this.clicks.filter(c=>c.button===2).length;
    const middleClicks = this.clicks.filter(c=>c.button===1).length;
    const clickIntervals = [];
    const clickHolds = [];
    for (let i = 0; i < this.clicks.length; i++) {
      const c = this.clicks[i];
      if (c.upTs && i>0) clickIntervals.push((c.downTs - this.clicks[i-1].downTs)/1000);
      if (c.upTs) clickHolds.push((c.upTs - c.downTs)/1000);
    }
    const meanClickInterval = clickIntervals.reduce((a,b)=>a+b,0)/clickIntervals.length || 0;
    const meanClickHold = clickHolds.reduce((a,b)=>a+b,0)/clickHolds.length || 0;

    // --- Scroll metrics ---
    const totalScrolls = this.scrolls.length;
    const scrollEventRateHz = totalScrolls / captureDurationSec;
    const scrollDeltas = this.scrolls.map(s => s.deltaY / window.innerHeight);
    const meanScrollDelta = scrollDeltas.reduce((a,b)=>a+b,0)/scrollDeltas.length || 0;
    const stdScrollDelta = Math.sqrt(scrollDeltas.reduce((a,b)=>a + (b-meanScrollDelta)**2,0)/scrollDeltas.length) || 0;
    let scrollDirectionChanges = 0;
    for (let i=1; i<scrollDeltas.length; i++){
      if (Math.sign(scrollDeltas[i]) !== Math.sign(scrollDeltas[i-1])) scrollDirectionChanges++;
    }

    // --- Heuristics ---
    const constantSpeedRatio = speeds.filter(s=>Math.abs(s-meanSpeedVal)/meanSpeedVal<0.1).length / (speeds.length || 1);
    const linearMovementRatio = pathEfficiencyRatio = netDistance / totalDistance || 0;
    const perfectStraightLinesCount = speeds.filter(s=>Math.abs(s-meanSpeedVal)/meanSpeedVal<0.01).length;
    const teleportEventCount = speeds.filter(s=>s > 5).length; // seuil arbitraire

    // --- Compose final object ---
    return {
      session_start_ts: this.sessionStart,
      elapsed_since_session_start_sec: elapsedSec,
      capture_duration_sec: captureDurationSec,
      total_events: moveEvents + totalClicks + totalScrolls,
      movement: {
        total_move_events: moveEvents,
        move_event_rate_hz: moveEventRateHz,
        total_distance_rel: totalDistance,
        net_displacement_rel: netDistance,
        path_efficiency_ratio: pathEfficiencyRatio,
        mean_speed_rel: meanSpeedVal,
        std_speed_rel: stdSpeed,
        max_speed_rel: Math.max(...speeds,0),
        min_speed_rel: Math.min(...speeds,0),
        mean_turning_angle_rad: meanAngle,
        std_turning_angle_rad: stdAngle,
        direction_changes_count: directionChanges,
        micro_movements_ratio: 0, // calcul possible si souhaité
        zero_delta_ratio: 0,
        jitter_index: 0
      },
      clicks: {
        total_click_events: totalClicks,
        left_click_count: leftClicks,
        right_click_count: rightClicks,
        middle_click_count: middleClicks,
        double_click_count: 0, // à calculer si nécessaire
        mean_click_interval_sec: meanClickInterval,
        std_click_interval_sec: 0, // à calculer si souhaité
        min_click_interval_sec: 0,
        max_click_interval_sec: 0,
        mean_click_hold_sec: meanClickHold,
        std_click_hold_sec: 0,
        max_click_hold_sec: 0,
        rapid_click_burst_count: 0,
        identical_interval_ratio: 0
      },
      scroll: {
        total_scroll_events: totalScrolls,
        scroll_event_rate_hz: scrollEventRateHz,
        mean_scroll_delta_rel: meanScrollDelta,
        std_scroll_delta_rel: stdScrollDelta,
        max_scroll_delta_rel: Math.max(...scrollDeltas,0),
        scroll_direction_changes: scrollDirectionChanges,
        continuous_scroll_sequences: 0,
        mean_scroll_interval_sec: 0
      },
      heuristics: {
        constant_speed_ratio: constantSpeedRatio,
        linear_movement_ratio: linearMovementRatio,
        perfect_straight_lines_count: perfectStraightLinesCount,
        teleport_event_count: teleportEventCount,
        event_uniformity_score: 0,
        entropy_direction: 0,
        entropy_speed: 0
      }
    };
  }

  // --- Reset buffers after each 5s batch ---
  resetBuffers() {
    this.moves = [];
    this.clicks = [];
    this.scrolls = [];
  }
}