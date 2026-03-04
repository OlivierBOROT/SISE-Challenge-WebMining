export function drawSpeedPlot () {
    "use strict";

    const WINDOW_MS = 15000;   // 15 s rolling window
    const CANVAS_H = 120;     // CSS px
    const PAD_L = 28;      // left padding for Y axis labels
    const PAD_R = 6;
    const PAD_T = 8;
    const PAD_B = 18;      // bottom padding for X axis labels
    const Y_GRIDLINES = 4;
    const SPEED_FLOOR = 800;     // minimum Y-axis ceiling (px/s)

    const samples = [];          // {t, speed}  t = performance.now()
    let lastX = null, lastY = null, lastT = null;
    let peakSpeed = 0;

    const canvas = document.getElementById('spCanvas');
    const ctx = canvas.getContext('2d');
    let dpr = 1, cssW = 0;

    /* ── Retina resize ── */
    function resize() {
        dpr = window.devicePixelRatio || 1;
        cssW = canvas.offsetWidth;
        canvas.width = Math.round(cssW * dpr);
        canvas.height = Math.round(CANVAS_H * dpr);
        canvas.style.width = cssW + 'px';
        canvas.style.height = CANVAS_H + 'px';
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener('resize', resize);

    /* ── Mouse tracking ── */
    document.addEventListener('mousemove', function (e) {
        const now = performance.now();
        const x = e.clientX, y = e.clientY;

        let speed = 0;
        if (lastT !== null) {
            const dist = Math.hypot(x - lastX, y - lastY);
            const dt = Math.max((now - lastT) / 1000, 0.001);
            speed = dist / dt;
        }
        lastX = x; lastY = y; lastT = now;

        samples.push({ t: now, speed });
    }, { passive: true });

    /* ── Map value → canvas Y (within plot area) ── */
    function toY(val, maxVal) {
        const plotH = CANVAS_H - PAD_T - PAD_B;
        return PAD_T + plotH * (1 - val / maxVal);
    }

    /* ── Draw ── */
    function draw() {
        requestAnimationFrame(draw);

        const now = performance.now();
        const cutoff = now - WINDOW_MS;

        // Prune old samples
        while (samples.length > 0 && samples[0].t < cutoff) samples.shift();

        ctx.clearRect(0, 0, cssW, CANVAS_H);

        const plotW = cssW - PAD_L - PAD_R;
        const plotH = CANVAS_H - PAD_T - PAD_B;

        // Dynamic Y ceiling — round up to nearest 200, min SPEED_FLOOR
        const maxSample = samples.reduce((m, s) => Math.max(m, s.speed), 0);
        const yCeil = Math.max(SPEED_FLOOR, Math.ceil(maxSample / 200) * 200);

        /* ── Grid lines ── */
        ctx.strokeStyle = '#e2e5ea';
        ctx.lineWidth = 0.5;
        ctx.setLineDash([3, 3]);
        ctx.fillStyle = '#bbb';
        ctx.font = `9px Arial`;
        ctx.textAlign = 'right';

        for (let i = 0; i <= Y_GRIDLINES; i++) {
            const val = (yCeil / Y_GRIDLINES) * i;
            const y = toY(val, yCeil);
            ctx.beginPath();
            ctx.moveTo(PAD_L, y);
            ctx.lineTo(PAD_L + plotW, y);
            ctx.stroke();
            // Y label
            const label = val >= 1000 ? (val / 1000).toFixed(1) + 'k' : String(Math.round(val));
            ctx.fillText(label, PAD_L - 4, y + 3);
        }
        ctx.setLineDash([]);

        /* ── X axis time labels ── */
        ctx.fillStyle = '#bbb';
        ctx.textAlign = 'center';
        ctx.font = '9px Arial';
        for (let s = 0; s <= 15; s += 5) {
            const x = PAD_L + plotW * (s / 15);
            ctx.fillText('-' + (15 - s) + 's', x, CANVAS_H - 4);
        }

        /* ── Axis lines ── */
        ctx.strokeStyle = '#d0d3d8';
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.moveTo(PAD_L, PAD_T);
        ctx.lineTo(PAD_L, PAD_T + plotH);
        ctx.lineTo(PAD_L + plotW, PAD_T + plotH);
        ctx.stroke();

        if (samples.length < 2) return;

        /* ── Map sample → canvas X ── */
        function toX(t) {
            return PAD_L + plotW * ((t - cutoff) / WINDOW_MS);
        }

        /* ── Filled area under curve ── */
        const baseY = PAD_T + plotH;

        ctx.beginPath();
        ctx.moveTo(toX(samples[0].t), baseY);
        for (let i = 0; i < samples.length; i++) {
            const x = toX(samples[i].t);
            const y = toY(samples[i].speed, yCeil);
            i === 0 ? ctx.lineTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.lineTo(toX(samples[samples.length - 1].t), baseY);
        ctx.closePath();

        const grad = ctx.createLinearGradient(0, PAD_T, 0, PAD_T + plotH);
        grad.addColorStop(0, 'rgba(228,121,17,0.18)');
        grad.addColorStop(1, 'rgba(240,192,64,0.03)');
        ctx.fillStyle = grad;
        ctx.fill();

        /* ── Line ── */
        ctx.beginPath();
        ctx.moveTo(toX(samples[0].t), toY(samples[0].speed, yCeil));
        for (let i = 1; i < samples.length; i++) {
            ctx.lineTo(toX(samples[i].t), toY(samples[i].speed, yCeil));
        }
        ctx.strokeStyle = '#e47911';
        ctx.lineWidth = 1.5;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.stroke();

        /* ── Live dot at head ── */
        const last = samples[samples.length - 1];
        const hx = toX(last.t);
        const hy = toY(last.speed, yCeil);
        ctx.beginPath();
        ctx.arc(hx, hy, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = '#232f3e';
        ctx.fill();

        /* ── Stats ── */
        const curSpeed = last.speed;
        const avgSpeed = samples.reduce((s, p) => s + p.speed, 0) / samples.length;
        if (curSpeed > peakSpeed) peakSpeed = curSpeed;

        document.getElementById('sp-cur').textContent = Math.round(curSpeed);
        document.getElementById('sp-avg').textContent = Math.round(avgSpeed);
        document.getElementById('sp-peak').textContent = Math.round(peakSpeed);
    }

    draw();
}