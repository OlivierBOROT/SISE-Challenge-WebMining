export function drawTrackPlot() {
  "use strict";

  const CANVAS_H_CSS = 180;
  const MAX_POINTS   = 250;
  const SPEED_MAX    = 800;
  const HEAT_RADIUS  = 18;

  // ── State ──
  const trail = [];
  let totalDist  = 0;
  let lastSpeed  = 0;
  let totalClicks = 0;

  // Heatmap grid (logical px, rebuilt on resize)
  let cssW = 0, dpr = 1;
  let grid = null;

  const canvas = document.getElementById('mtCanvas');
  const ctx    = canvas.getContext('2d');

  // Off-screen canvas for heatmap ImageData compositing
  const hmCanvas = document.createElement('canvas');
  const hmCtx    = hmCanvas.getContext('2d');

  // ── Resize ──
  function resize() {
    dpr  = window.devicePixelRatio || 1;
    cssW = canvas.offsetWidth;

    canvas.width        = Math.round(cssW * dpr);
    canvas.height       = Math.round(CANVAS_H_CSS * dpr);
    canvas.style.width  = cssW + 'px';
    canvas.style.height = CANVAS_H_CSS + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    hmCanvas.width  = cssW;
    hmCanvas.height = CANVAS_H_CSS;

    grid = new Float32Array(cssW * CANVAS_H_CSS);
  }
  resize();
  window.addEventListener('resize', resize);

  // ── Coordinate mapping ──
  function toCanvas(px, py) {
    return {
      x: (px / window.innerWidth)  * cssW,
      y: (py / window.innerHeight) * CANVAS_H_CSS,
    };
  }

  // ── Heatmap: add blob ──
  function addHeat(cx, cy) {
    const r  = HEAT_RADIUS;
    const x0 = Math.max(0, Math.floor(cx - r));
    const x1 = Math.min(cssW - 1, Math.ceil(cx + r));
    const y0 = Math.max(0, Math.floor(cy - r));
    const y1 = Math.min(CANVAS_H_CSS - 1, Math.ceil(cy + r));
    const sigma2 = 2 * (r / 2.5) ** 2;
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const d = Math.hypot(x - cx, y - cy);
        if (d <= r) grid[y * cssW + x] += Math.exp(-(d * d) / sigma2);
      }
    }
  }

  // ── Heatmap: color ramp ──
  function heatColor(t) {
    if (t <= 0) return [0, 0, 0, 0];
    let r, g, b, a;
    if (t < 0.4) {
      const s = t / 0.4;
      r = Math.round(240 * s); g = Math.round(192 * s); b = Math.round(64 * s); a = s * 0.65;
    } else {
      const s = (t - 0.4) / 0.6;
      r = Math.round(240 + s * (228 - 240));
      g = Math.round(192 + s * (121 - 192));
      b = Math.round(64  + s * (17  - 64));
      a = 0.65 + s * 0.3;
    }
    return [r, g, b, Math.min(1, a)];
  }

  // ── Heatmap: bake to off-screen canvas ──
  function bakeHeatmap() {
    let maxVal = 0;
    for (let i = 0; i < grid.length; i++) if (grid[i] > maxVal) maxVal = grid[i];
    if (maxVal === 0) { hmCtx.clearRect(0, 0, cssW, CANVAS_H_CSS); return; }

    const imgData = hmCtx.createImageData(cssW, CANVAS_H_CSS);
    const data    = imgData.data;
    for (let i = 0; i < grid.length; i++) {
      const [r, g, b, a] = heatColor(grid[i] / maxVal);
      const p = i * 4;
      data[p] = r; data[p+1] = g; data[p+2] = b; data[p+3] = Math.round(a * 255);
    }
    hmCtx.putImageData(imgData, 0, 0);
  }

  // ── Trail: segment color ──
  function segmentColor(speed, alpha) {
    const t = Math.min(speed / SPEED_MAX, 1);
    const r = Math.round(240 + t * (228 - 240));
    const g = Math.round(192 + t * (121 - 192));
    const b = Math.round(64  + t * (17  - 64));
    return `rgba(${r},${g},${b},${alpha})`;
  }

  // ── Event listeners ──
  document.addEventListener('mousemove', function (e) {
    const now = performance.now();
    const { x, y } = toCanvas(e.clientX, e.clientY);
    let speed = 0;
    if (trail.length > 0) {
      const prev = trail[trail.length - 1];
      const dist = Math.hypot(x - prev.x, y - prev.y);
      const dt   = Math.max((now - prev.t) / 1000, 0.001);
      speed      = dist / dt;
      totalDist += dist;
    }
    lastSpeed = speed;
    trail.push({ x, y, t: now, speed });
    if (trail.length > MAX_POINTS) trail.shift();
  }, { passive: true });

  document.addEventListener('mousedown', function (e) {
    totalClicks++;
    const { x, y } = toCanvas(e.clientX, e.clientY);
    addHeat(x, y);
    bakeHeatmap();
    document.getElementById('hm-total').textContent = totalClicks;
  });

  // ── Render loop ──
  function draw() {
    requestAnimationFrame(draw);

    ctx.clearRect(0, 0, cssW, CANVAS_H_CSS);

    // 1. Heatmap layer (from off-screen canvas)
    ctx.drawImage(hmCanvas, 0, 0, cssW, CANVAS_H_CSS);

    // 2. Trail layer on top
    if (trail.length >= 2) {
      for (let i = 1; i < trail.length; i++) {
        const p   = trail[i - 1], q = trail[i];
        const age = i / trail.length;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(q.x, q.y);
        ctx.strokeStyle = segmentColor(q.speed, Math.pow(age, 1.8) * 0.95);
        ctx.lineWidth   = 0.8 + age * 1.6;
        ctx.lineCap     = 'round';
        ctx.lineJoin    = 'round';
        ctx.stroke();
      }

      // Head dot
      const h = trail[trail.length - 1];
      ctx.beginPath();
      ctx.arc(h.x, h.y, 2.5, 0, Math.PI * 2);
      ctx.fillStyle = '#232f3e';
      ctx.fill();
    }

    // Stats
    document.getElementById('mt-dist').textContent = Math.round(totalDist);
    document.getElementById('mt-spd').textContent  = Math.round(lastSpeed);
  }
  draw();

  // ── Reset ──
  document.addEventListener('inputTrackerReset', () => {
      trail.length = 0; totalDist = 0; lastSpeed = 0; totalClicks = 0;
        grid.fill(0);
        hmCtx.clearRect(0, 0, cssW, CANVAS_H_CSS);
        ctx.clearRect(0, 0, cssW, CANVAS_H_CSS);
        document.getElementById('hm-total').textContent = 0;
        document.getElementById('mt-dist').textContent  = 0;
        document.getElementById('mt-spd').textContent   = 0;
    });

}