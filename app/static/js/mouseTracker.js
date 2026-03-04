/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║  MouseTracker  –  Raw data collection & feature computation     ║
 * ║                                                                  ║
 * ║  Captures every signal useful for:                               ║
 * ║    • UX / behaviour analysis  (heatmaps, funnels, engagement)   ║
 * ║    • Bot detection            (timing regularity, jitter, etc.) ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 *  Usage:
 *      const tracker = new MouseTracker();
 *      tracker.start();
 *      // … later …
 *      const features = tracker.computeFeatures();   // {speed_avg, …}
 *      const snapshot = tracker.getSnapshot();        // richer object for UI
 */

"use strict";

/* ═══════════════════════════════════════════
   §1  MATH HELPERS
   ═══════════════════════════════════════════ */

const _math = {
    dist(a, b) {
        return Math.hypot(b.x - a.x, b.y - a.y);
    },

    /** Signed angle at point B in the polyline A→B→C  (radians). */
    angleBetween(a, b, c) {
        const v1x = b.x - a.x, v1y = b.y - a.y;
        const v2x = c.x - b.x, v2y = c.y - b.y;
        return Math.atan2(v1x * v2y - v1y * v2x, v1x * v2x + v1y * v2y);
    },

    /** Menger curvature at B in A→B→C. */
    curvature(a, b, c) {
        const ab = this.dist(a, b), bc = this.dist(b, c), ca = this.dist(c, a);
        const area = Math.abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)) / 2;
        const denom = ab * bc * ca;
        return denom === 0 ? 0 : (4 * area) / denom;
    },

    mean(arr) { return arr.length ? arr.reduce((s, v) => s + v, 0) / arr.length : 0; },
    median(arr) {
        if (!arr.length) return 0;
        const sorted = [...arr].sort((a, b) => a - b);
        const mid = sorted.length >> 1;
        return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    },
    stddev(arr) {
        if (arr.length < 2) return 0;
        const m = this.mean(arr);
        return Math.sqrt(arr.reduce((s, v) => s + (v - m) ** 2, 0) / (arr.length - 1));
    },
    min(arr) { return arr.length ? Math.min(...arr) : 0; },
    max(arr) { return arr.length ? Math.max(...arr) : 0; },

    /**
     * Shannon entropy of a histogram (array of counts).
     * Useful to measure regularity of time intervals.
     */
    entropy(counts) {
        const total = counts.reduce((s, v) => s + v, 0);
        if (total === 0) return 0;
        let h = 0;
        for (const c of counts) {
            if (c === 0) continue;
            const p = c / total;
            h -= p * Math.log2(p);
        }
        return h;
    },

    /** Bin an array of values into `nBins` equal-width bins, return counts. */
    histogram(arr, nBins = 10) {
        if (!arr.length) return new Array(nBins).fill(0);
        const lo = Math.min(...arr), hi = Math.max(...arr);
        const range = hi - lo || 1;
        const bins = new Array(nBins).fill(0);
        for (const v of arr) {
            const idx = Math.min(nBins - 1, Math.floor(((v - lo) / range) * nBins));
            bins[idx]++;
        }
        return bins;
    },

    /** Coefficient of variation = std / mean (0 = perfectly constant). */
    cv(arr) {
        const m = this.mean(arr);
        return m === 0 ? 0 : this.stddev(arr) / m;
    },

    /** Percentile (0-100) of a sorted array. */
    percentile(sorted, p) {
        if (!sorted.length) return 0;
        const idx = (p / 100) * (sorted.length - 1);
        const lo = Math.floor(idx), hi = Math.ceil(idx);
        return lo === hi ? sorted[lo] : sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
    },
};


/* ═══════════════════════════════════════════
   §2  MouseTracker CLASS
   ═══════════════════════════════════════════ */

class MouseTracker {
    constructor() {
        /* ── Ring-buffer configuration ── */
        this.MAX_MOVE_EVENTS = 5000;   // ~30-80 s of data at 60-144 Hz
        this.MAX_CLICK_EVENTS = 500;
        this.MAX_SCROLL_EVENTS = 1000;
        this.MAX_KEY_EVENTS = 500;

        /* ── Raw event buffers ── */
        this.moves   = [];   // {x, y, t, mx, my}  (mx/my = movementX/Y)
        this.clicks  = [];   // {x, y, t, btn, target}
        this.scrolls = [];   // {x, y, dx, dy, t}
        this.keys    = [];   // {key, t, type}  (type = 'down' | 'up')

        /* ── Cumulative counters ── */
        this.totalDist      = 0;
        this.totalClicks    = 0;
        this.totalScrollDy  = 0;
        this.totalKeys      = 0;

        /* ── Timing ── */
        this.sessionStart   = performance.now();
        this.lastMoveT      = 0;
        this.lastClickT     = 0;
        this.lastScrollT    = 0;

        /* ── Idle / pause detection ── */
        this.IDLE_THRESHOLD = 500;   // ms – no movement ⇒ considered idle
        this.idleTime       = 0;     // ms
        this.pauseCount     = 0;
        this._inPause       = false;

        /* ── Distance accumulator tracking ── */
        this._distIdx = 0;

        /* ── Visibility ── */
        this.tabBlurCount   = 0;
        this.tabHiddenTime  = 0;
        this._lastHiddenAt  = null;

        /* ── First event flags (bot detection) ── */
        this.firstMoveDelay = null;   // ms from page load to first move
        this.firstClickDelay = null;
        this.entryPoint     = null;   // {x, y} of first move

        /* ── Speed history for sparkline ── */
        this.speedHistory = [];

        /* ── Bound handlers (for cleanup) ── */
        this._onMove   = this._handleMove.bind(this);
        this._onClick  = this._handleClick.bind(this);
        this._onScroll = this._handleScroll.bind(this);
        this._onKeyDown = this._handleKeyDown.bind(this);
        this._onKeyUp   = this._handleKeyUp.bind(this);
        this._onVisibility = this._handleVisibility.bind(this);
    }

    /* ──────────────────── Lifecycle ──────────────────── */

    start() {
        document.addEventListener("mousemove",        this._onMove,   { passive: true });
        document.addEventListener("click",            this._onClick,  { passive: true });
        document.addEventListener("contextmenu",      this._onClick,  { passive: true });
        document.addEventListener("wheel",            this._onScroll, { passive: true });
        document.addEventListener("keydown",          this._onKeyDown,{ passive: true });
        document.addEventListener("keyup",            this._onKeyUp,  { passive: true });
        document.addEventListener("visibilitychange", this._onVisibility);
    }

    stop() {
        document.removeEventListener("mousemove",        this._onMove);
        document.removeEventListener("click",            this._onClick);
        document.removeEventListener("contextmenu",      this._onClick);
        document.removeEventListener("wheel",            this._onScroll);
        document.removeEventListener("keydown",          this._onKeyDown);
        document.removeEventListener("keyup",            this._onKeyUp);
        document.removeEventListener("visibilitychange", this._onVisibility);
    }

    /* ──────────────────── Event handlers ──────────────────── */

    _handleMove(e) {
        const now = performance.now();

        const pt = {
            x:  e.clientX,
            y:  e.clientY,
            t:  now,
            mx: e.movementX ?? null,   // null if UA doesn't support it
            my: e.movementY ?? null,
        };
        this.moves.push(pt);
        if (this.moves.length > this.MAX_MOVE_EVENTS) this.moves.shift();

        // First-move metadata
        if (this.firstMoveDelay === null) {
            this.firstMoveDelay = now - this.sessionStart;
            this.entryPoint = { x: pt.x, y: pt.y };
        }

        // Idle / pause tracking
        if (this.lastMoveT > 0) {
            const gap = now - this.lastMoveT;
            if (gap > this.IDLE_THRESHOLD) {
                this.idleTime += gap;
                if (!this._inPause) { this.pauseCount++; this._inPause = true; }
            } else {
                this._inPause = false;
            }
        }
        this.lastMoveT = now;
    }

    _handleClick(e) {
        const now = performance.now();
        this.clicks.push({
            x: e.clientX,
            y: e.clientY,
            t: now,
            btn: e.button,                         // 0=left,1=mid,2=right
            target: e.target?.tagName ?? "?",      // element clicked
        });
        if (this.clicks.length > this.MAX_CLICK_EVENTS) this.clicks.shift();

        this.totalClicks++;
        if (this.firstClickDelay === null) this.firstClickDelay = now - this.sessionStart;
        this.lastClickT = now;
    }

    _handleScroll(e) {
        const now = performance.now();
        this.scrolls.push({
            x: e.clientX, y: e.clientY,
            dx: e.deltaX, dy: e.deltaY,
            t: now,
        });
        if (this.scrolls.length > this.MAX_SCROLL_EVENTS) this.scrolls.shift();
        this.totalScrollDy += Math.abs(e.deltaY);
        this.lastScrollT = now;
    }

    _handleKeyDown(e) {
        this.keys.push({ key: e.key, t: performance.now(), type: "down" });
        if (this.keys.length > this.MAX_KEY_EVENTS) this.keys.shift();
        this.totalKeys++;
    }
    _handleKeyUp(e) {
        this.keys.push({ key: e.key, t: performance.now(), type: "up" });
        if (this.keys.length > this.MAX_KEY_EVENTS) this.keys.shift();
    }

    _handleVisibility() {
        if (document.hidden) {
            this._lastHiddenAt = performance.now();
            this.tabBlurCount++;
        } else if (this._lastHiddenAt !== null) {
            this.tabHiddenTime += performance.now() - this._lastHiddenAt;
            this._lastHiddenAt = null;
        }
    }

    /* ═══════════════════════════════════════════════════════
       §3  FEATURE COMPUTATION
       ═══════════════════════════════════════════════════════
       Returns a flat dict of all features, ready to send
       to the Isolation Forest endpoint.
    */

    computeFeatures() {
        const now = performance.now();
        const ev = this.moves;
        const n = ev.length;
        if (n < 3) return null;

        const elapsed = (now - this.sessionStart) / 1000;   // seconds

        // ── 1. Inter-event time deltas (dt) ────────────────
        const dts = [];          // ms
        for (let i = 1; i < n; i++) dts.push(ev[i].t - ev[i - 1].t);

        const dtSorted = [...dts].sort((a, b) => a - b);
        const dt_mean   = _math.mean(dts);
        const dt_std    = _math.stddev(dts);
        const dt_cv     = _math.cv(dts);        // low ⇒ bot (too regular)
        const dt_min    = _math.min(dts);
        const dt_max    = _math.max(dts);
        const dt_median = _math.median(dts);
        const dt_entropy = _math.entropy(_math.histogram(dts, 20));

        // ── 2. Speeds (px/s) ────────────────
        const speeds = [];
        let freshDist = 0;
        for (let i = 1; i < n; i++) {
            const d = _math.dist(ev[i - 1], ev[i]);
            const dt = dts[i - 1] / 1000;
            freshDist += d;
            if (dt > 0) speeds.push(d / dt);
        }

        // Accumulate total distance
        for (let i = Math.max(1, this._distIdx); i < n; i++) {
            this.totalDist += _math.dist(ev[i - 1], ev[i]);
        }
        this._distIdx = n;

        const speed_avg = _math.mean(speeds);
        const speed_std = _math.stddev(speeds);
        const speed_max = _math.max(speeds);
        const speed_min = _math.min(speeds);
        const speed_median = _math.median(speeds);

        // ── 3. Accelerations (px/s²) ────────────────
        const accels = [];
        for (let i = 1; i < speeds.length; i++) {
            const dt = dts[i] / 1000 || 0.001;
            accels.push((speeds[i] - speeds[i - 1]) / dt);
        }
        const accel_avg = _math.mean(accels.map(Math.abs));
        const accel_std = _math.stddev(accels);
        const accel_max = _math.max(accels.map(Math.abs));

        // ── 4. Jerk (derivative of acceleration, px/s³) ──
        const jerks = [];
        for (let i = 1; i < accels.length; i++) {
            const dt = dts[i + 1] / 1000 || 0.001;
            jerks.push((accels[i] - accels[i - 1]) / dt);
        }
        const jerk_avg = _math.mean(jerks.map(Math.abs));
        const jerk_std = _math.stddev(jerks);
        const jerk_max = _math.max(jerks.map(Math.abs));

        // ── 5. Angular velocity (°/s) ────────────────
        const angVels = [];
        for (let i = 1; i < n - 1; i++) {
            const angle = _math.angleBetween(ev[i - 1], ev[i], ev[i + 1]);
            const dt = (ev[i + 1].t - ev[i - 1].t) / 1000 || 0.001;
            angVels.push(Math.abs(angle * (180 / Math.PI)) / dt);
        }
        const ang_vel_avg = _math.mean(angVels);
        const ang_vel_std = _math.stddev(angVels);

        // ── 6. Trajectory geometry ────────────────
        const angles = [], curvatures = [];
        let dirChanges = 0;
        for (let i = 1; i < n - 1; i++) {
            const a = _math.angleBetween(ev[i - 1], ev[i], ev[i + 1]);
            angles.push(a);
            curvatures.push(_math.curvature(ev[i - 1], ev[i], ev[i + 1]));
            if (angles.length >= 2) {
                if (angles[angles.length - 1] * angles[angles.length - 2] < 0) dirChanges++;
            }
        }

        let pathLen = 0;
        for (let i = 1; i < n; i++) pathLen += _math.dist(ev[i - 1], ev[i]);
        const displacement = _math.dist(ev[0], ev[n - 1]);
        const straightness = pathLen > 0 ? displacement / pathLen : 1;
        const sinuosity    = displacement > 0 ? pathLen / displacement : 1;

        const curvature_avg = _math.mean(curvatures);
        const curvature_std = _math.stddev(curvatures);
        const angle_avg     = _math.mean(angles.map(Math.abs)) * (180 / Math.PI);
        const angle_std     = _math.stddev(angles) * (180 / Math.PI);

        // ── 7. Micro-jitter (last 200 ms) ────────────────
        //    Humans have natural hand tremor ≈8-12 Hz.
        //    Bots either have ZERO jitter or artificial jitter.
        const jitterWin = ev.filter(e => now - e.t < 200);
        const jitterDisps = [];
        for (let i = 1; i < jitterWin.length; i++) {
            jitterDisps.push(_math.dist(jitterWin[i - 1], jitterWin[i]));
        }
        const jitter        = _math.stddev(jitterDisps);
        const jitter_mean   = _math.mean(jitterDisps);
        const jitter_hz     = jitterWin.length > 1 ? 1000 * (jitterWin.length - 1) / 200 : 0;
        const jitter_score  = speed_avg > 0 ? (jitter * jitter_hz) / speed_avg : 0;

        // ── 8. Sub-pixel / integer coordinate analysis ──
        //    Bots often produce only integer coordinates.
        //    Real mice can have fractional `movementX/Y`.
        let intCoordCount = 0;
        let hasMovementData = 0;
        for (const p of ev) {
            if (p.x === Math.round(p.x) && p.y === Math.round(p.y)) intCoordCount++;
            if (p.mx !== null) hasMovementData++;
        }
        const int_coord_ratio     = n > 0 ? intCoordCount / n : 1;
        const has_movement_ratio  = n > 0 ? hasMovementData / n : 0;

        // ── 9. Movement-X/Y consistency check ──
        //    Compare cumulative movementX/Y with actual position delta.
        //    Discrepancy may indicate synthetic events.
        let sumMx = 0, sumMy = 0;
        for (const p of ev) { sumMx += p.mx ?? 0; sumMy += p.my ?? 0; }
        const posDeltaX = ev[n - 1].x - ev[0].x;
        const posDeltaY = ev[n - 1].y - ev[0].y;
        const movement_drift_x = hasMovementData > 0 ? Math.abs(sumMx - posDeltaX) : -1;
        const movement_drift_y = hasMovementData > 0 ? Math.abs(sumMy - posDeltaY) : -1;

        // ── 10. Scroll features ────────────────
        const scrollDts = [];
        for (let i = 1; i < this.scrolls.length; i++) {
            scrollDts.push(this.scrolls[i].t - this.scrolls[i - 1].t);
        }
        const scroll_count      = this.scrolls.length;
        const scroll_dy_total   = this.totalScrollDy;
        const scroll_dt_cv      = _math.cv(scrollDts);   // regularity check

        // ── 11. Click features ────────────────
        const clickDts = [];
        for (let i = 1; i < this.clicks.length; i++) {
            clickDts.push(this.clicks[i].t - this.clicks[i - 1].t);
        }
        const click_dt_cv       = _math.cv(clickDts);
        const click_dt_mean     = _math.mean(clickDts);

        // Time between last move and each click (humans decelerate before clicking)
        const moveToClickDelays = [];
        for (const cl of this.clicks) {
            // Find last move event before this click
            let lastMove = null;
            for (let i = this.moves.length - 1; i >= 0; i--) {
                if (this.moves[i].t <= cl.t) { lastMove = this.moves[i]; break; }
            }
            if (lastMove) moveToClickDelays.push(cl.t - lastMove.t);
        }
        const move_to_click_delay_avg = _math.mean(moveToClickDelays);

        // ── 12. Activity / session ────────────────
        const events_per_sec = elapsed > 0 ? n / elapsed : 0;
        const clicks_per_sec = elapsed > 0 ? this.totalClicks / elapsed : 0;
        const idle_ratio     = elapsed > 0 ? (this.idleTime / 1000) / elapsed : 0;

        // ── 13. Keyboard presence ──
        const has_keyboard_activity = this.totalKeys > 0 ? 1 : 0;
        const keys_per_sec = elapsed > 0 ? this.totalKeys / elapsed : 0;

        // ── 14. Tab visibility ──
        const tab_blur_count = this.tabBlurCount;
        const tab_hidden_ratio = elapsed > 0 ? (this.tabHiddenTime / 1000) / elapsed : 0;

        // ── 15. Entry behaviour ──
        const first_move_delay = this.firstMoveDelay ?? -1;
        const first_click_delay = this.firstClickDelay ?? -1;

        // ── 16. Speed history for sparkline ──
        this.speedHistory.push(speed_avg);
        if (this.speedHistory.length > 60) this.speedHistory.shift();

        // ── 17. Recent points for trajectory viz ──
        const RECENT_MS = 2000;
        const recentPoints = ev.filter(e => now - e.t < RECENT_MS);

        // ════════════════════ RETURN ════════════════════
        return {
            // ── Timing ──
            dt_mean, dt_std, dt_cv, dt_min, dt_max, dt_median, dt_entropy,

            // ── Speed ──
            speed_avg, speed_std, speed_max, speed_min, speed_median,
            speed_inst: speeds.length ? speeds[speeds.length - 1] : 0,

            // ── Acceleration ──
            accel_avg, accel_std, accel_max,
            accel_inst: accels.length ? Math.abs(accels[accels.length - 1]) : 0,

            // ── Jerk ──
            jerk_avg, jerk_std, jerk_max,

            // ── Angular velocity ──
            ang_vel_avg, ang_vel_std,

            // ── Trajectory geometry ──
            curvature_avg, curvature_std,
            angle_avg, angle_std,
            dir_changes: dirChanges,
            straightness, sinuosity,

            // ── Micro-jitter ──
            jitter, jitter_mean, jitter_hz, jitter_score,

            // ── Coordinate integrity (bot detection) ──
            int_coord_ratio, has_movement_ratio,
            movement_drift_x, movement_drift_y,

            // ── Scroll ──
            scroll_count, scroll_dy_total, scroll_dt_cv,

            // ── Clicks ──
            total_clicks: this.totalClicks,
            clicks_per_sec, click_dt_cv, click_dt_mean,
            move_to_click_delay_avg,

            // ── Idle / pauses ──
            idle_ratio, pause_count: this.pauseCount,
            idle_time: this.idleTime / 1000,

            // ── Activity ──
            events_per_sec, total_events: n,
            elapsed,
            total_dist: this.totalDist,

            // ── Keyboard ──
            has_keyboard_activity, keys_per_sec,

            // ── Tab ──
            tab_blur_count, tab_hidden_ratio,

            // ── Entry behaviour ──
            first_move_delay, first_click_delay,
            entry_x: this.entryPoint?.x ?? -1,
            entry_y: this.entryPoint?.y ?? -1,

            // ── UI helpers (not sent to backend) ──
            _recentPoints:  recentPoints,
            _speedHistory:  this.speedHistory,
            _clicks:        this.clicks,
            _pos:           { x: ev[n - 1].x, y: ev[n - 1].y },
        };
    }

    /**
     * Extract only the features consumed by the Isolation Forest.
     * Everything prefixed with _ is stripped (UI-only helpers).
     */
    getDetectionPayload() {
        const all = this.computeFeatures();
        if (!all) return null;
        const payload = {};
        for (const [k, v] of Object.entries(all)) {
            if (!k.startsWith("_")) payload[k] = v;
        }
        return payload;
    }

    /**
     * Return the last N raw move events (for server-side storage).
     */
    getRecentRawEvents(n = 200) {
        return this.moves.slice(-n).map(e => ({
            x: e.x, y: e.y, t: Math.round(e.t),
            mx: e.mx, my: e.my,
        }));
    }

    /**
     * Trim old events to avoid memory buildup.
     * Call periodically (e.g. every 10 s).
     */
    trim(keepMs = 10000) {
        const cutoff = performance.now() - keepMs;
        while (this.moves.length > 0 && this.moves[0].t < cutoff) {
            this.moves.shift();
        }
        this._distIdx = Math.max(0, this._distIdx - 1);
        while (this.scrolls.length > 0 && this.scrolls[0].t < cutoff) {
            this.scrolls.shift();
        }
    }
}
