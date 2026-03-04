/**
 * MouseTracker — Collecte d'événements souris & calcul des features.
 *
 * Produit un objet structuré identique au modèle Pydantic
 * MouseBehaviorFeatures (session, movement, clicks, scroll, heuristics).
 */

"use strict";

/* ═══════════ Helpers mathématiques ═══════════ */

function _dist(a, b) { return Math.hypot(b.x - a.x, b.y - a.y); }

function _mean(arr) {
    if (!arr.length) return 0;
    let s = 0;
    for (let i = 0; i < arr.length; i++) s += arr[i];
    return s / arr.length;
}

function _stddev(arr) {
    if (arr.length < 2) return 0;
    const m = _mean(arr);
    let s = 0;
    for (let i = 0; i < arr.length; i++) s += (arr[i] - m) ** 2;
    return Math.sqrt(s / (arr.length - 1));
}

function _min(arr) {
    if (!arr.length) return 0;
    let m = arr[0];
    for (let i = 1; i < arr.length; i++) if (arr[i] < m) m = arr[i];
    return m;
}

function _max(arr) {
    if (!arr.length) return 0;
    let m = arr[0];
    for (let i = 1; i < arr.length; i++) if (arr[i] > m) m = arr[i];
    return m;
}

/** Angle signé au point B dans la polyligne A→B→C (radians). */
function _angle(a, b, c) {
    const v1x = b.x - a.x, v1y = b.y - a.y;
    const v2x = c.x - b.x, v2y = c.y - b.y;
    return Math.atan2(v1x * v2y - v1y * v2x, v1x * v2x + v1y * v2y);
}

/** Entropie de Shannon d'un tableau de comptages. */
function _entropy(counts) {
    let total = 0;
    for (let i = 0; i < counts.length; i++) total += counts[i];
    if (total === 0) return 0;
    let h = 0;
    for (let i = 0; i < counts.length; i++) {
        if (counts[i] === 0) continue;
        const p = counts[i] / total;
        h -= p * Math.log2(p);
    }
    return h;
}

/** Histogramme : répartit arr dans nBins bins de largeur égale. */
function _histogram(arr, nBins) {
    if (!arr.length) return new Array(nBins).fill(0);
    let lo = arr[0], hi = arr[0];
    for (let i = 1; i < arr.length; i++) {
        if (arr[i] < lo) lo = arr[i];
        if (arr[i] > hi) hi = arr[i];
    }
    const range = hi - lo || 1;
    const bins = new Array(nBins).fill(0);
    for (let i = 0; i < arr.length; i++) {
        const idx = Math.min(nBins - 1, Math.floor(((arr[i] - lo) / range) * nBins));
        bins[idx]++;
    }
    return bins;
}

/* ═══════════ Classe MouseTracker ═══════════ */

class MouseTracker {
    constructor() {
        this.moves = [];          // {x, y, t}
        this.clicks = [];         // {t, btn}
        this.clickHolds = [];     // durées en ms
        this.scrolls = [];        // {dy, t}
        this._pendingDown = {};   // btn → timestamp

        this.sessionStart = Date.now();           // timestamp absolu (ms)
        this.captureStart = performance.now();    // pour durées relatives

        this._onMove  = this._handleMove.bind(this);
        this._onDown  = this._handleDown.bind(this);
        this._onUp    = this._handleUp.bind(this);
        this._onWheel = this._handleWheel.bind(this);
    }

    /* ── Cycle de vie ── */

    start() {
        document.addEventListener("mousemove", this._onMove,  { passive: true });
        document.addEventListener("mousedown", this._onDown,  { passive: true });
        document.addEventListener("mouseup",   this._onUp,    { passive: true });
        document.addEventListener("wheel",     this._onWheel, { passive: true });
    }

    stop() {
        document.removeEventListener("mousemove", this._onMove);
        document.removeEventListener("mousedown", this._onDown);
        document.removeEventListener("mouseup",   this._onUp);
        document.removeEventListener("wheel",     this._onWheel);
    }

    /* ── Handlers ── */

    _handleMove(e) {
        this.moves.push({ x: e.clientX, y: e.clientY, t: performance.now() });
    }

    _handleDown(e) {
        const t = performance.now();
        this.clicks.push({ t, btn: e.button });
        this._pendingDown[e.button] = t;
    }

    _handleUp(e) {
        const t = performance.now();
        const downT = this._pendingDown[e.button];
        if (downT !== undefined) {
            this.clickHolds.push(t - downT);
            delete this._pendingDown[e.button];
        }
    }

    _handleWheel(e) {
        this.scrolls.push({ dy: e.deltaY, t: performance.now() });
    }

    /** Réinitialise tous les buffers pour une nouvelle fenêtre de 5 s. */
    reset() {
        this.moves       = [];
        this.clicks      = [];
        this.clickHolds  = [];
        this.scrolls     = [];
        this._pendingDown = {};
        this.sessionStart = Date.now();
        this.captureStart = performance.now();
    }

    /* ══════════════════════════════════════════════
       Calcul des features — structure identique
       au modèle Pydantic MouseBehaviorFeatures
       ══════════════════════════════════════════════ */

    computeFeatures() {
        const mv = this.moves;
        const n  = mv.length;
        if (n < 3) return null;

        const diag  = Math.hypot(window.innerWidth, window.innerHeight);
        const viewH = window.innerHeight;
        const elapsed    = (Date.now() - this.sessionStart) / 1000;
        const captureDur = (mv[n - 1].t - mv[0].t) / 1000;

        /* ───── Deltas inter-événements (secondes) & distances (px) ───── */
        const dts   = [];
        const dists = [];
        for (let i = 1; i < n; i++) {
            dts.push((mv[i].t - mv[i - 1].t) / 1000);
            dists.push(_dist(mv[i - 1], mv[i]));
        }

        const totalDist = dists.reduce((s, v) => s + v, 0);
        const netDisp   = _dist(mv[0], mv[n - 1]);

        /* ───── Vitesses normalisées (diag/s) ───── */
        const speeds = [];
        for (let i = 0; i < dists.length; i++) {
            if (dts[i] > 0) speeds.push((dists[i] / diag) / dts[i]);
        }

        /* ───── Accélérations normalisées (diag/s²) ───── */
        const accels = [];
        for (let i = 1; i < speeds.length; i++) {
            if (dts[i] > 0) accels.push((speeds[i] - speeds[i - 1]) / dts[i]);
        }

        /* ───── Angles de virage (radians) ───── */
        const angles = [];
        let dirChanges = 0;
        for (let i = 1; i < n - 1; i++) {
            const a = _angle(mv[i - 1], mv[i], mv[i + 1]);
            angles.push(a);
            if (angles.length >= 2 && angles[angles.length - 1] * angles[angles.length - 2] < 0) {
                dirChanges++;
            }
        }

        /* ───── Micro-mouvements & deltas nuls ───── */
        let microCount = 0, zeroCount = 0;
        for (let i = 0; i < dists.length; i++) {
            if (dists[i] < 2) microCount++;
            if (dists[i] === 0) zeroCount++;
        }

        const movement = {
            total_move_events:       n,
            move_event_rate_hz:      elapsed > 0 ? n / elapsed : 0,
            mean_delta_time_sec:     _mean(dts),
            std_delta_time_sec:      _stddev(dts),
            min_delta_time_sec:      _min(dts),
            max_delta_time_sec:      _max(dts),
            total_distance_rel:      diag > 0 ? totalDist / diag : 0,
            net_displacement_rel:    diag > 0 ? netDisp / diag : 0,
            path_efficiency_ratio:   totalDist > 0 ? netDisp / totalDist : 0,
            mean_speed_rel:          _mean(speeds),
            std_speed_rel:           _stddev(speeds),
            max_speed_rel:           _max(speeds),
            min_speed_rel:           _min(speeds),
            mean_acceleration_rel:   _mean(accels.map(Math.abs)),
            std_acceleration_rel:    _stddev(accels),
            max_acceleration_rel:    _max(accels.map(Math.abs)),
            mean_turning_angle_rad:  _mean(angles),
            std_turning_angle_rad:   _stddev(angles),
            direction_changes_count: dirChanges,
            micro_movements_ratio:   dists.length > 0 ? microCount / dists.length : 0,
            zero_delta_ratio:        dists.length > 0 ? zeroCount / dists.length : 0,
            jitter_index:            _mean(dists) > 0 ? _stddev(dists) / _mean(dists) : 0,
        };

        /* ═════ CLICKS ═════ */
        const cl = this.clicks;
        let leftCount = 0, rightCount = 0, midCount = 0;
        for (const c of cl) {
            if (c.btn === 0) leftCount++;
            else if (c.btn === 2) rightCount++;
            else if (c.btn === 1) midCount++;
        }

        const clickInts = [];
        for (let i = 1; i < cl.length; i++) clickInts.push((cl[i].t - cl[i - 1].t) / 1000);

        // Double-clics : deux clics gauche consécutifs < 300 ms
        const leftClicks = cl.filter(c => c.btn === 0);
        let doubleClicks = 0;
        for (let i = 1; i < leftClicks.length; i++) {
            if ((leftClicks[i].t - leftClicks[i - 1].t) < 300) doubleClicks++;
        }

        // Durées de maintien (secondes)
        const holds = this.clickHolds.map(h => h / 1000);

        // Rafales rapides : ≥ 3 clics en < 500 ms
        let rapidBursts = 0;
        for (let i = 0; i < cl.length; i++) {
            let j = i + 1;
            while (j < cl.length && (cl[j].t - cl[i].t) < 500) j++;
            if (j - i >= 3) { rapidBursts++; i = j - 1; }
        }

        // Ratio d'intervalles identiques (tolérance 5 ms)
        let identicalCount = 0;
        for (let i = 1; i < clickInts.length; i++) {
            if (Math.abs(clickInts[i] - clickInts[i - 1]) < 0.005) identicalCount++;
        }

        const clicks = {
            total_click_events:        cl.length,
            left_click_count:          leftCount,
            right_click_count:         rightCount,
            middle_click_count:        midCount,
            double_click_count:        doubleClicks,
            mean_click_interval_sec:   _mean(clickInts),
            std_click_interval_sec:    _stddev(clickInts),
            min_click_interval_sec:    _min(clickInts),
            max_click_interval_sec:    _max(clickInts),
            mean_click_hold_sec:       _mean(holds),
            std_click_hold_sec:        _stddev(holds),
            max_click_hold_sec:        _max(holds),
            rapid_click_burst_count:   rapidBursts,
            identical_interval_ratio:  clickInts.length >= 2
                ? identicalCount / (clickInts.length - 1) : 0,
        };

        /* ═════ SCROLL ═════ */
        const sc = this.scrolls;
        const scrollDeltasRel = [];
        for (const s of sc) scrollDeltasRel.push(Math.abs(s.dy) / viewH);

        const scrollInts = [];
        for (let i = 1; i < sc.length; i++) scrollInts.push((sc[i].t - sc[i - 1].t) / 1000);

        let scrollDirChanges = 0;
        for (let i = 1; i < sc.length; i++) {
            if (sc[i].dy * sc[i - 1].dy < 0) scrollDirChanges++;
        }

        let contSequences = 0, inSeq = false;
        for (let i = 1; i < sc.length; i++) {
            if ((sc[i].t - sc[i - 1].t) < 200) {
                if (!inSeq) { contSequences++; inSeq = true; }
            } else { inSeq = false; }
        }

        const scroll = {
            total_scroll_events:          sc.length,
            scroll_event_rate_hz:         elapsed > 0 ? sc.length / elapsed : 0,
            mean_scroll_delta_rel:        _mean(scrollDeltasRel),
            std_scroll_delta_rel:         _stddev(scrollDeltasRel),
            max_scroll_delta_rel:         _max(scrollDeltasRel),
            scroll_direction_changes:     scrollDirChanges,
            continuous_scroll_sequences:  contSequences,
            mean_scroll_interval_sec:     _mean(scrollInts),
        };

        /* ═════ HEURISTIQUES ═════ */
        const meanSpd = _mean(speeds);
        let constantCount = 0;
        for (const s of speeds) {
            if (meanSpd > 0 && Math.abs(s - meanSpd) / meanSpd < 0.1) constantCount++;
        }

        let linearCount = 0;
        for (const a of angles) {
            if (Math.abs(a) < 0.087) linearCount++;   // < 5°
        }

        // Lignes droites parfaites : segments de ≥ 3 points colinéaires (angle < ~1°)
        let perfectLines = 0, streak = 0;
        for (const a of angles) {
            if (Math.abs(a) < 0.02) { streak++; }
            else { if (streak >= 2) perfectLines++; streak = 0; }
        }
        if (streak >= 2) perfectLines++;

        // Téléportations : saut > 30 % de la diagonale
        let teleportCount = 0;
        const teleThresh = diag * 0.3;
        for (const d of dists) { if (d > teleThresh) teleportCount++; }

        // Uniformité : 1 − CV des Δt (borné 0–1)
        const dtCv = _mean(dts) > 0 ? _stddev(dts) / _mean(dts) : 0;

        // Entropie directionnelle (8 bins cardinaux)
        const dirBins = new Array(8).fill(0);
        for (let i = 1; i < n; i++) {
            const a = Math.atan2(mv[i].y - mv[i - 1].y, mv[i].x - mv[i - 1].x);
            dirBins[Math.floor(((a + Math.PI) / (2 * Math.PI)) * 8) % 8]++;
        }

        const heuristics = {
            constant_speed_ratio:         speeds.length > 0 ? constantCount / speeds.length : 0,
            linear_movement_ratio:        angles.length > 0 ? linearCount / angles.length : 0,
            perfect_straight_lines_count: perfectLines,
            teleport_event_count:         teleportCount,
            event_uniformity_score:       Math.max(0, Math.min(1, 1 - dtCv)),
            entropy_direction:            _entropy(dirBins),
            entropy_speed:                _entropy(_histogram(speeds, 10)),
        };

        /* ═════ RÉSULTAT ═════ */
        return {
            session_start_ts:                this.sessionStart,
            elapsed_since_session_start_sec: elapsed,
            capture_duration_sec:            captureDur,
            movement,
            clicks,
            scroll,
            heuristics,
        };
    }
}
