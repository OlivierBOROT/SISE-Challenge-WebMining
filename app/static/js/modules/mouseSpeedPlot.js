export function drawSpeedPlot() {
    "use strict";

    const WINDOW_MS = 15000;
    const CANVAS_H = 180;
    const PAD_L = 28, PAD_R = 6, PAD_T = 8, PAD_B = 18;
    const Y_GRIDLINES = 4;
    const SPEED_FLOOR = 800;

    const samples = [];
    let lastX = 0, lastY = 0, lastT = 0;
    let peakSpeed = 0;

    const canvas = document.getElementById('spCanvas');
    const ctx = canvas.getContext('2d');
    let dpr = 1, cssW = 0;

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

    document.addEventListener('mousemove', function (e) {
        const now = performance.now();
        const x = e.clientX, y = e.clientY;
        let speed = 0;
        if (lastT !== null) {
            speed = Math.hypot(x - lastX, y - lastY) / Math.max((now - lastT) / 1000, 0.001);
        }
        lastX = x; lastY = y; lastT = now;
        samples.push({ t: now, speed });
    }, { passive: true });

    // Inject zero-speed samples during idle so the line drops to 0 rather than freezing.
    setInterval(function () {
        const now = performance.now();
        if (lastT !== null && now - lastT > 80) {
            samples.push({ t: now, speed: 0 });
        }
    }, 100);

    function toY(val, maxVal) {
        return PAD_T + (CANVAS_H - PAD_T - PAD_B) * (1 - val / maxVal);
    }

    function draw() {
        requestAnimationFrame(draw);

        const now = performance.now();
        const cutoff = now - WINDOW_MS;
        while (samples.length > 0 && samples[0].t < cutoff) samples.shift();

        ctx.clearRect(0, 0, cssW, CANVAS_H);

        const plotW = cssW - PAD_L - PAD_R;
        const plotH = CANVAS_H - PAD_T - PAD_B;
        const maxSample = samples.reduce((m, s) => Math.max(m, s.speed), 0);
        const yCeil = Math.max(SPEED_FLOOR, Math.ceil(maxSample / 200) * 200);

        // Grid lines
        ctx.strokeStyle = '#e2e5ea'; ctx.lineWidth = 0.5; ctx.setLineDash([3, 3]);
        ctx.fillStyle = '#bbb'; ctx.font = '9px Arial'; ctx.textAlign = 'right';
        for (let i = 0; i <= Y_GRIDLINES; i++) {
            const val = (yCeil / Y_GRIDLINES) * i;
            const y = toY(val, yCeil);
            ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(PAD_L + plotW, y); ctx.stroke();
            ctx.fillText(val >= 1000 ? (val / 1000).toFixed(1) + 'k' : Math.round(val), PAD_L - 4, y + 3);
        }
        ctx.setLineDash([]);

        // X labels
        ctx.fillStyle = '#bbb'; ctx.textAlign = 'center'; ctx.font = '9px Arial';
        for (let s = 0; s <= 15; s += 5) {
            ctx.fillText('-' + (15 - s) + 's', PAD_L + plotW * (s / 15), CANVAS_H - 4);
        }

        // Axes
        ctx.strokeStyle = '#d0d3d8'; ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.moveTo(PAD_L, PAD_T); ctx.lineTo(PAD_L, PAD_T + plotH); ctx.lineTo(PAD_L + plotW, PAD_T + plotH);
        ctx.stroke();

        if (samples.length < 2) return;

        const toX = t => PAD_L + plotW * ((t - cutoff) / WINDOW_MS);
        const baseY = PAD_T + plotH;

        // Fill
        ctx.beginPath();
        ctx.moveTo(toX(samples[0].t), baseY);
        for (const s of samples) ctx.lineTo(toX(s.t), toY(s.speed, yCeil));
        ctx.lineTo(toX(samples[samples.length - 1].t), baseY);
        ctx.closePath();
        const grad = ctx.createLinearGradient(0, PAD_T, 0, PAD_T + plotH);
        grad.addColorStop(0, 'rgba(228,121,17,0.18)');
        grad.addColorStop(1, 'rgba(240,192,64,0.03)');
        ctx.fillStyle = grad; ctx.fill();

        // Line
        ctx.beginPath();
        ctx.moveTo(toX(samples[0].t), toY(samples[0].speed, yCeil));
        for (let i = 1; i < samples.length; i++) ctx.lineTo(toX(samples[i].t), toY(samples[i].speed, yCeil));
        ctx.strokeStyle = '#e47911'; ctx.lineWidth = 1.5;
        ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.stroke();

        // Head dot
        const last = samples[samples.length - 1];
        ctx.beginPath();
        ctx.arc(toX(last.t), toY(last.speed, yCeil), 2.5, 0, Math.PI * 2);
        ctx.fillStyle = '#232f3e'; ctx.fill();

        // Stats
        const cur = last.speed;
        const avg = samples.reduce((s, p) => s + p.speed, 0) / samples.length;
        if (cur > peakSpeed) peakSpeed = cur;
        document.getElementById('sp-cur').textContent = Math.round(cur);
        document.getElementById('sp-avg').textContent = Math.round(avg);
        document.getElementById('sp-peak').textContent = Math.round(peakSpeed);
    }

    draw();

    // ── Reset ──
    document.addEventListener('inputTrackerReset', () => {
        samples.length = 0;
        lastX = lastY = lastT = 0;
        peakSpeed = 0;
        ctx.clearRect(0, 0, cssW, CANVAS_H);
        document.getElementById('sp-cur').textContent = '0';
        document.getElementById('sp-avg').textContent = '0';
        document.getElementById('sp-peak').textContent = '0';
    });
}