/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║  StatsPanel  –  Dashboard UI & server communication             ║
 * ║                                                                  ║
 * ║  • Updates the right-side stats panel every second               ║
 * ║  • Draws trajectory, sparkline, heatmap canvases                 ║
 * ║  • Sends features to /ajax/detect for bot classification         ║
 * ║  • Flushes raw events to /ajax/mouse for server storage          ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 *  Depends on: MouseTracker (mouseTracker.js loaded before this file)
 */

"use strict";

/* ═══════════════════════════════════════════
   §1  INIT
   ═══════════════════════════════════════════ */

const tracker = new MouseTracker();
tracker.start();

const $ = id => document.getElementById(id);
function fmt(v, d = 1) {
    return typeof v === "number" && isFinite(v) ? v.toFixed(d) : "–";
}


/* ═══════════════════════════════════════════
   §2  DOM UPDATER
   ═══════════════════════════════════════════ */

function updateDOM(s) {
    if (!s) return;

    // Position
    $("sX").textContent = fmt(s._pos.x, 0);
    $("sY").textContent = fmt(s._pos.y, 0);
    $("sDist").textContent = fmt(s.total_dist, 0) + " px";

    // Speed
    $("sSpd").textContent     = fmt(s.speed_inst, 1);
    $("sSpdAvg").textContent  = fmt(s.speed_avg, 1);
    $("sSpdMax").textContent  = fmt(s.speed_max, 1);
    $("sSpdStd").textContent  = fmt(s.speed_std, 1);
    $("sSpdMin").textContent  = fmt(s.speed_min, 1);
    $("sSpdMed").textContent  = fmt(s.speed_median, 1);

    // Acceleration
    $("sAcc").textContent     = fmt(s.accel_inst, 1);
    $("sAccAvg").textContent  = fmt(s.accel_avg, 1);
    $("sAccMax").textContent  = fmt(s.accel_max, 1);
    $("sAccStd").textContent  = fmt(s.accel_std, 1);

    // Jerk
    $("sJerkAvg").textContent = fmt(s.jerk_avg, 0);
    $("sJerkMax").textContent = fmt(s.jerk_max, 0);

    // Angular velocity
    $("sAngVel").textContent  = fmt(s.ang_vel_avg, 1);
    $("sAngVelStd").textContent = fmt(s.ang_vel_std, 1);

    // Geometry
    $("sCurv").textContent       = fmt(s.curvature_avg, 4);
    $("sCurvStd").textContent    = fmt(s.curvature_std, 4);
    $("sAngle").textContent      = fmt(s.angle_avg, 1);
    $("sAngleStd").textContent   = fmt(s.angle_std, 1);
    $("sDirChanges").textContent = s.dir_changes;
    $("sStraight").textContent   = fmt(s.straightness, 3);
    $("sSinuosity").textContent  = fmt(s.sinuosity, 2);

    // Micro-jitter
    $("sJitter").textContent      = fmt(s.jitter, 2);
    $("sJitterMean").textContent  = fmt(s.jitter_mean, 2);
    $("sJitterHz").textContent    = fmt(s.jitter_hz, 0);
    $("sJitterScore").textContent = fmt(s.jitter_score, 3);

    // Timing regularity (bot indicators)
    $("sDtMean").textContent    = fmt(s.dt_mean, 2) + " ms";
    $("sDtStd").textContent     = fmt(s.dt_std, 2) + " ms";
    $("sDtCv").textContent      = fmt(s.dt_cv, 3);
    $("sDtEntropy").textContent = fmt(s.dt_entropy, 2);
    $("sIntCoord").textContent  = fmt(s.int_coord_ratio * 100, 1) + "%";
    $("sMovRatio").textContent  = fmt(s.has_movement_ratio * 100, 1) + "%";

    // Clicks & pauses
    $("sClicks").textContent = s.total_clicks;
    $("sCPS").textContent    = fmt(s.clicks_per_sec, 2);
    $("sIdle").textContent   = fmt(s.idle_time, 1);
    $("sPauses").textContent = s.pause_count;
    $("sClickDtCv").textContent = fmt(s.click_dt_cv, 3);
    $("sMoveToClick").textContent = fmt(s.move_to_click_delay_avg, 1) + " ms";

    // Scroll
    $("sScrollCount").textContent = s.scroll_count;
    $("sScrollDy").textContent    = fmt(s.scroll_dy_total, 0) + " px";
    $("sScrollCv").textContent    = fmt(s.scroll_dt_cv, 3);

    // Activity
    $("sEPS").textContent   = fmt(s.events_per_sec, 1);
    $("sTotal").textContent = s.total_events;
    $("sTime").textContent  = fmt(s.elapsed, 1);
    $("sKPS").textContent   = fmt(s.keys_per_sec, 2);

    // Entry
    $("sFirstMove").textContent  = fmt(s.first_move_delay, 0) + " ms";
    $("sFirstClick").textContent = s.first_click_delay >= 0 ? fmt(s.first_click_delay, 0) + " ms" : "–";

    // Draw canvases
    drawTrajectory(s._recentPoints);
    drawSpeedSparkline(s._speedHistory);
    drawHeatmap(s._clicks);
}


/* ═══════════════════════════════════════════
   §3  CANVAS RENDERING
   ═══════════════════════════════════════════ */

function drawTrajectory(pts) {
    const c = $("trajCanvas");
    const ctx = c.getContext("2d");
    c.width = c.clientWidth * devicePixelRatio;
    c.height = c.clientHeight * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    const w = c.clientWidth, h = c.clientHeight;
    ctx.clearRect(0, 0, w, h);
    if (pts.length < 2) return;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    pts.forEach(p => { minX = Math.min(minX, p.x); minY = Math.min(minY, p.y); maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y); });
    const rangeX = maxX - minX || 1, rangeY = maxY - minY || 1;
    const pad = 10;
    const sx = (w - 2 * pad) / rangeX, sy = (h - 2 * pad) / rangeY, sc = Math.min(sx, sy);
    const ox = pad + (w - 2 * pad - rangeX * sc) / 2, oy = pad + (h - 2 * pad - rangeY * sc) / 2;

    ctx.beginPath();
    ctx.strokeStyle = "#a29bfe";
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    pts.forEach((p, i) => {
        const px = ox + (p.x - minX) * sc, py = oy + (p.y - minY) * sc;
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    });
    ctx.stroke();

    const first = pts[0], last = pts[pts.length - 1];
    [[first, "#00cec9"], [last, "#fd79a8"]].forEach(([p, col]) => {
        ctx.beginPath();
        ctx.fillStyle = col;
        ctx.arc(ox + (p.x - minX) * sc, oy + (p.y - minY) * sc, 3, 0, Math.PI * 2);
        ctx.fill();
    });
}

function drawSpeedSparkline(data) {
    const c = $("speedCanvas");
    const ctx = c.getContext("2d");
    c.width = c.clientWidth * devicePixelRatio;
    c.height = c.clientHeight * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    const w = c.clientWidth, h = c.clientHeight;
    ctx.clearRect(0, 0, w, h);
    if (data.length < 2) return;

    const max = Math.max(...data, 1);
    const step = w / (data.length - 1);

    ctx.beginPath();
    ctx.moveTo(0, h);
    data.forEach((v, i) => ctx.lineTo(i * step, h - (v / max) * (h - 10)));
    ctx.lineTo(w, h);
    ctx.closePath();
    const grd = ctx.createLinearGradient(0, 0, 0, h);
    grd.addColorStop(0, "rgba(108,92,231,.4)");
    grd.addColorStop(1, "rgba(108,92,231,.02)");
    ctx.fillStyle = grd;
    ctx.fill();

    ctx.beginPath();
    ctx.strokeStyle = "#6c5ce7";
    ctx.lineWidth = 1.5;
    data.forEach((v, i) => {
        const px = i * step, py = h - (v / max) * (h - 10);
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    });
    ctx.stroke();
}

function drawHeatmap(clicks) {
    const c = $("heatCanvas");
    const ctx = c.getContext("2d");
    c.width = c.clientWidth * devicePixelRatio;
    c.height = c.clientHeight * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    const w = c.clientWidth, h = c.clientHeight;
    ctx.clearRect(0, 0, w, h);
    if (!clicks || !clicks.length) return;

    const pageW = window.innerWidth, pageH = window.innerHeight;
    clicks.forEach(cl => {
        const cx = (cl.x / pageW) * w, cy = (cl.y / pageH) * h;
        const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, 18);
        grd.addColorStop(0, "rgba(253,121,168,.6)");
        grd.addColorStop(1, "rgba(253,121,168,0)");
        ctx.fillStyle = grd;
        ctx.beginPath();
        ctx.arc(cx, cy, 18, 0, Math.PI * 2);
        ctx.fill();
    });
}


/* ═══════════════════════════════════════════
   §4  SERVER COMMUNICATION
   ═══════════════════════════════════════════ */

/** Flush raw events to /ajax/mouse for storage. */
function flushToServer() {
    const batch = tracker.getRecentRawEvents(200);
    if (!batch.length) return;
    fetch("/ajax/mouse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: batch }),
    }).catch(() => { });
}

/** Send features to /ajax/detect for Isolation Forest scoring. */
function sendBotDetection() {
    const features = tracker.getDetectionPayload();
    if (!features || features.elapsed < 2) return;

    fetch("/ajax/detect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ features }),
    })
        .then(r => r.json())
        .then(data => {
            if (data.status !== "ok") return;
            updateBotUI(data);
        })
        .catch(() => { });
}

function updateBotUI(data) {
    const badge = $("botBadge");
    const label = $("botLabel");
    const sub = $("botSub");
    const bar = $("botConfBar");

    const isBot = data.label === "bot";
    badge.className = "bot-badge " + (isBot ? "bot" : "human");
    badge.querySelector(".icon").textContent = isBot ? "🤖" : "👤";
    label.textContent = isBot ? "BOT détecté" : "Humain";
    sub.textContent = `Score: ${data.score.toFixed(4)} · Confiance: ${(data.confidence * 100).toFixed(0)}%`;

    bar.style.width = (data.confidence * 100) + "%";
    bar.style.background = isBot ? "#d63031" : "#00b894";

    $("sIFScore").textContent = data.score.toFixed(4);
    $("sIFConf").textContent = (data.confidence * 100).toFixed(1) + "%";
    $("sIFPred").textContent = data.label.toUpperCase();
    $("sIFPred").style.color = isBot ? "#d63031" : "#00b894";
}


/* ═══════════════════════════════════════════
   §5  TICK LOOPS
   ═══════════════════════════════════════════ */

// Stats refresh: 1 Hz
setInterval(() => {
    const features = tracker.computeFeatures();
    updateDOM(features);
}, 1000);

// Flush raw events to server: every 5 s
setInterval(flushToServer, 5000);

// Bot detection: every 3 s
setInterval(sendBotDetection, 3000);

// Trim old events: every 10 s
setInterval(() => tracker.trim(10000), 10000);
