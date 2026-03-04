/**
 * StatsPanel — Affichage des features & détection bot.
 *
 * • Met à jour le panneau de stats toutes les 5 secondes
 * • Envoie les features à /ajax/detect pour l'Isolation Forest
 *
 * Dépend de : MouseTracker (mouseTracker.js chargé avant ce fichier)
 */

"use strict";

const tracker = new MouseTracker();
tracker.start();

const $ = id => document.getElementById(id);

/* ═══════════ Formatage automatique ═══════════
   Adapte la précision selon la convention de nommage du champ. */

function fmt(key, val) {
    if (typeof val !== "number" || !isFinite(val)) return "–";
    if (/_count$|_events$/.test(key))   return val.toString();
    if (/_ratio$/.test(key))            return (val * 100).toFixed(1) + " %";
    if (/_sec$/.test(key))              return val.toFixed(4);
    if (/_hz$/.test(key))               return val.toFixed(1);
    if (/_rad$/.test(key))              return val.toFixed(4);
    if (/index$|score$/.test(key))      return val.toFixed(3);
    return val.toFixed(4);
}

/* ═══════════ Mise à jour du DOM ═══════════
   Itère sur les clés de l'objet et cherche un élément id = prefix + key. */

function updateSection(obj, prefix) {
    for (const [key, val] of Object.entries(obj)) {
        const el = $(prefix + key);
        if (el) el.textContent = fmt(key, val);
    }
}

/* ═══════════ Aplatir les features pour le backend ═══════════ */

function flatten(features) {
    const flat = {};
    for (const [key, val] of Object.entries(features)) {
        if (val !== null && typeof val === "object") Object.assign(flat, val);
        else flat[key] = val;
    }
    return flat;
}

/* ═══════════ Détection bot ═══════════ */

function sendBotDetection(features) {
    const flat = flatten(features);

    fetch("/ajax/detect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ features: flat }),
    })
    .then(r => r.json())
    .then(data => {
        if (data.status !== "ok") return;
        const isBot = data.label === "bot";
        const badge = $("botBadge");
        badge.className = "bot-badge " + (isBot ? "bot" : "human");
        badge.querySelector(".icon").textContent = isBot ? "🤖" : "👤";
        $("botLabel").textContent = isBot ? "BOT détecté" : "Humain";
        $("botSub").textContent =
            "Score : " + data.score.toFixed(4) +
            " · Confiance : " + (data.confidence * 100).toFixed(0) + " %";
        $("botConfBar").style.width = (data.confidence * 100) + "%";
        $("botConfBar").style.background = isBot ? "#d63031" : "#00b894";
    })
    .catch(() => {});
}

/* ═══════════ Boucle principale — toutes les 5 s ═══════════ */

function update() {
    const f = tracker.computeFeatures();
    if (!f) return;

    /* Session */
    $("sSessionStart").textContent = new Date(f.session_start_ts).toLocaleTimeString();
    $("sElapsed").textContent      = f.elapsed_since_session_start_sec.toFixed(1) + " s";
    $("sCapture").textContent      = f.capture_duration_sec.toFixed(1) + " s";

    /* Sections automatiques */
    updateSection(f.movement,   "m_");
    updateSection(f.clicks,     "c_");
    updateSection(f.scroll,     "s_");
    updateSection(f.heuristics, "h_");

    /* Bot detection */
    sendBotDetection(f);

    /* Reset pour la prochaine fenêtre de 5 s */
    tracker.reset();
}

setInterval(update, 5000);
