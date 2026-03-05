// ── Cluster definitions
const CLUSTERS = [
    { id: "hysterique", label: "Hystérique", desc: "Mouvements et actions très rapides, clics frénétiques.", color: "#e84545", bg: "#fff5f5", border: "#fca5a5" },
    { id: "explorateur", label: "Explorateur", desc: "Navigation lente et méthodique, exploration large.", color: "#2563eb", bg: "#eff6ff", border: "#93c5fd" },
    { id: "precis", label: "Précis", desc: "Trajectoires directes, peu de clics, haute efficacité.", color: "#16a34a", bg: "#f0fdf4", border: "#86efac" },
    { id: "indecis", label: "Indécis", desc: "Allers-retours fréquents, hésitations marquées.", color: "#d97706", bg: "#fffbeb", border: "#fcd34d" },
    { id: "passif", label: "Passif", desc: "Très peu de mouvement, longues pauses, faible activité.", color: "#7c3aed", bg: "#f5f3ff", border: "#c4b5fd" },
];

// Render the cluster list on load
export function initUserResult () {
    const container = document.getElementById("cluster-all");
    CLUSTERS.forEach(c => {
        const el = document.createElement("div");
        el.className = "cluster-option";
        el.id = "cluster-opt-" + c.id;
        el.style.setProperty("--c-text", c.color);
        el.style.setProperty("--c-bg", c.bg);
        el.style.setProperty("--c-border", c.border);
        el.innerHTML = `<div class="cluster-option-dot" style="background:${c.color}"></div><span class="cluster-option-name">${c.label}</span><span class="cluster-option-desc">${c.desc}</span>`;
        container.appendChild(el);
    });

    const descriptions = document.querySelector('#cluster-widget .descriptions');
    const moreButton = document.querySelector('#cluster-more-button');
    moreButton.addEventListener('click', () => {
        if (descriptions.classList.contains('open')) {
            descriptions.classList.remove('open');
            moreButton.textContent = "Voir plus";
        } else {
            descriptions.classList.add('open');
            moreButton.textContent = "Voir moins";
        }
    })

    setClusterResult("hysterique");
}

export function setClusterResult(clusterId) {
    const c = CLUSTERS.find(x => x.id === clusterId);
    if (!c) return;

    // Show result header
    document.getElementById("cluster-pending").style.display = "none";
    document.getElementById("cluster-result").style.display = "block";
    document.getElementById("cluster-badge").style.visibility = "visible";

    // Pill
    document.getElementById("cluster-pill-wrap").innerHTML =
        `<span class="cluster-pill" style="color:${c.color};background:${c.bg};border-color:${c.border}"><span class="cluster-pill-dot"></span>${c.label}</span>`;

    // Name + desc
    document.getElementById("cluster-name").textContent = c.label;
    document.getElementById("cluster-name").style.color = c.color;
    document.getElementById("cluster-desc").textContent = c.desc;

    // Highlight active option in list
    CLUSTERS.forEach(x => {
        const el = document.getElementById("cluster-opt-" + x.id);
        el.classList.toggle("active", x.id === clusterId);
    });
}