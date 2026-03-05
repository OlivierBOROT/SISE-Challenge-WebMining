export function drawScatterPlot(initialData = null) {

    const PAD = 24;        // padding inside canvas (logical px)
    const DOT_R = 3;       // default dot radius
    const DOT_R_HI = 5;    // highlighted dot radius
    const CANVAS_H = 180;
    // ── Live user point ──
    let userPoint   = null; // { x, y, label } — current rendered position
    let userTarget  = null; // { x, y, label } — target position
    let animating   = false;
    const LERP      = 0.12;  // 0–1, lower = slower/smoother

    // ── Cluster color map (same ids as CLUSTERS array) ──
    const CLUSTER_COLORS = {
        0: "#e84545",
        1: "#2563eb",
        2: "#16a34a",
        3: "#d97706",
        4: "#7c3aed",
        5: "#94a3b8",
    };

    let data = initialData;   // { x: [], y: [], label: [] }  label optional
    let activeCluster = null;

    const canvas = document.getElementById("scatterCanvas");
    const ctx = canvas.getContext("2d");
    let dpr = 1, cssW = 0;

    // Tooltip element
    const tooltip = document.createElement("div");
    tooltip.className = "scatter-tooltip";
    document.body.appendChild(tooltip);

    // ── Resize ──
    function resize() {
        dpr = window.devicePixelRatio || 1;
        cssW = canvas.offsetWidth;
        canvas.width = Math.round(cssW * dpr);
        canvas.height = Math.round(CANVAS_H * dpr);
        canvas.style.width = cssW + "px";
        canvas.style.height = CANVAS_H + "px";
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        if (data) render();
    }
    resize();
    window.addEventListener("tabSwitch", resize);

    // ── Compute axis bounds with padding ──
    function bounds(arr) {
        let lo = Infinity, hi = -Infinity;
        for (const v of arr) { if (v < lo) lo = v; if (v > hi) hi = v; }
        const margin = (hi - lo) * 0.08 || 1;
        return { lo: lo - margin, hi: hi + margin };
    }

    // ── Map data → canvas coords ──
    function makeMappers(bx, by) {
        const plotW = cssW - PAD * 2;
        const plotH = CANVAS_H - PAD * 2;
        return {
            toX: v => PAD + ((v - bx.lo) / (bx.hi - bx.lo)) * plotW,
            toY: v => PAD + (1 - (v - by.lo) / (by.hi - by.lo)) * plotH,
        };
    }

    // ── Draw axis lines + tick label ──
    function drawAxes(bx, by, toX, toY) {
        ctx.strokeStyle = "#e2e5ea";
        ctx.lineWidth = 0.5;
        ctx.setLineDash([3, 3]);
        ctx.fillStyle = "#ccc";
        ctx.font = "8px Arial";

        // 4 vertical gridlines
        for (let i = 0; i <= 4; i++) {
            const v = bx.lo + (bx.hi - bx.lo) * (i / 4);
            const x = toX(v);
            ctx.beginPath(); ctx.moveTo(x, PAD); ctx.lineTo(x, CANVAS_H - PAD); ctx.stroke();
            ctx.textAlign = "center";
            ctx.fillText(v.toFixed(1), x, CANVAS_H - PAD + 10);
        }

        // 4 horizontal gridlines
        for (let i = 0; i <= 4; i++) {
            const v = by.lo + (by.hi - by.lo) * (i / 4);
            const y = toY(v);
            ctx.beginPath(); ctx.moveTo(PAD, y); ctx.lineTo(cssW - PAD, y); ctx.stroke();
            ctx.textAlign = "right";
            ctx.fillText(v.toFixed(1), PAD - 3, y + 3);
        }

        ctx.setLineDash([]);

        // Border
        ctx.strokeStyle = "#d0d3d8";
        ctx.lineWidth = 0.8;
        ctx.strokeRect(PAD, PAD, cssW - PAD * 2, CANVAS_H - PAD * 2);
    }

    // ── Main render ──
    function render() {
        if (!data || !data.x || !data.x.length) return;

        ctx.clearRect(0, 0, cssW, CANVAS_H);

        const bx = bounds(data.x);
        const by = bounds(data.y);
        const { toX, toY } = makeMappers(bx, by);

        drawAxes(bx, by, toX, toY);

        const n = data.x.length;

        // Draw all dots — dimmed if a cluster is active
        for (let i = 0; i < n; i++) {
            const label = data.label ? data.label[i] : null;
            const color = CLUSTER_COLORS[label] || CLUSTER_COLORS.default;
            const isActive = activeCluster === null || label === activeCluster;
            const x = toX(data.x[i]);
            const y = toY(data.y[i]);

            ctx.beginPath();
            ctx.arc(x, y, DOT_R, 0, Math.PI * 2);
            ctx.fillStyle = isActive ? color + "cc" : color + "22";
            ctx.fill();

            if (isActive) {
                ctx.strokeStyle = color + "66";
                ctx.lineWidth = 0.5;
                ctx.stroke();
            }
        }

        renderUserPoint(toX, toY);

        document.getElementById("sc-n").textContent = n;
    }

    // ── Tooltip on hover ──
    canvas.addEventListener("mousemove", function (e) {
        if (!data) return;
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const bx = bounds(data.x);
        const by = bounds(data.y);
        const { toX, toY } = makeMappers(bx, by);
        const n = data.x.length;
        let best = null, bestD = 10;   // 10px snap radius

        for (let i = 0; i < n; i++) {
            const d = Math.hypot(toX(data.x[i]) - mx, toY(data.y[i]) - my);
            if (d < bestD) { bestD = d; best = i; }
        }

        if (best !== null) {
            tooltip.style.opacity = "1";
            tooltip.style.left = (e.clientX + 12) + "px";
            tooltip.style.top = (e.clientY - 20) + "px";
            const lbl = data.label ? data.label[best] : "?";
            tooltip.textContent = `x: ${data.x[best].toFixed(3)}  y: ${data.y[best].toFixed(3)}  [${lbl}]`;
        } else {
            tooltip.style.opacity = "0";
        }
    });

    canvas.addEventListener("mouseleave", function () {
        tooltip.style.opacity = "0";
    });

    // ── Public API ──

    /**
     * Load data into the scatter plot.
     * @param {{ x: number[], y: number[], label?: string[] }} d
     *   label: optional array of cluster ids (same as CLUSTERS ids)
     */
    window.setScatterData = function (d) {
        data = d;
        document.getElementById("scatter-badge").style.visibility = "visible";
        render();
    };

    /**
     * Highlight a single cluster (dims all others).
     * Pass null to reset.
     */
    window.highlightCluster = function (clusterId) {
        activeCluster = clusterId;
        const el = document.getElementById("sc-highlighted");
        el.textContent = clusterId
            ? (CLUSTERS.find(c => c.id === clusterId)?.label || clusterId)
            : "—";
        if (clusterId) {
            el.style.color = CLUSTER_COLORS[clusterId] || "#232f3e";
        } else {
            el.style.color = "#232f3e";
        }
        render();
    };

    function animatePoint() {
        if (!userPoint || !userTarget) { animating = false; return; }

        userPoint.x     = userPoint.x     + (userTarget.x     - userPoint.x)     * LERP;
        userPoint.y     = userPoint.y     + (userTarget.y     - userPoint.y)     * LERP;
        userPoint.label = userTarget.label; // snap label immediately

        const dx = Math.abs(userTarget.x - userPoint.x);
        const dy = Math.abs(userTarget.y - userPoint.y);

        render();

        if (dx > 0.001 || dy > 0.001) {
            requestAnimationFrame(animatePoint);
        } else {
            userPoint.x = userTarget.x; // snap to exact target
            userPoint.y = userTarget.y;
            animating = false;
            render();
        }
    }

    function renderUserPoint(toX, toY) {
        if (!userPoint) return;
        const color = CLUSTER_COLORS[userPoint.label] || CLUSTER_COLORS.default;
        const cx = toX(userPoint.x);
        const cy = toY(userPoint.y);

        // Outer ring
        ctx.beginPath();
        ctx.arc(cx, cy, DOT_R_HI + 3, 0, Math.PI * 2);
        ctx.strokeStyle = color + "55";
        ctx.lineWidth   = 1.5;
        ctx.stroke();

        // Filled dot
        ctx.beginPath();
        ctx.arc(cx, cy, DOT_R_HI, 0, Math.PI * 2);
        ctx.fillStyle   = color;
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth   = 1.5;
        ctx.stroke();
    }

    // ── Auto-highlight when cluster widget changes ──
    // Patch setClusterResult to also highlight scatter
    const _origSet = window.setClusterResult;
    if (_origSet) {
        window.setClusterResult = function (id) {
            _origSet(id);
            window.highlightCluster(id);
        };
    }
    const _origClear = window.clearClusterResult;
    if (_origClear) {
        window.clearClusterResult = function () {
            _origClear();
            window.highlightCluster(null);
        };
    }

    if (data) {
        document.getElementById("scatter-badge").style.visibility = "visible";
        render();
    }

    document.addEventListener('behaviourUpdate', (e) => {
        const { x, y, label } = e.detail;
        userTarget = { x, y, label };

        // Snap to target on first placement, animate on subsequent moves
        if (!userPoint) {
            userPoint = { ...userTarget };
            render();
            return;
        }

        if (!animating) {
            animating = true;
            animatePoint();
        }
    })
}