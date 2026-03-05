export function setBotResult(label, score) {
    const widget = document.getElementById("bot-widget");
    const elScore = document.getElementById("bot-score");
    const elBar = document.getElementById("bot-bar");
    const elStatus = document.getElementById("bot-status");

    widget.classList.remove("is-bot", "is-human");

    elScore.textContent = score.toFixed(2);
    elBar.style.width = (score * 100) + "%";

    if (label === "bot") {
        widget.classList.add("is-bot");
        elStatus.textContent = "⚠ Bot";
    } else {
        widget.classList.add("is-human");
        elStatus.textContent = "✓ Human";
    }
}

export function clearBotResult() {
    const widget = document.getElementById("bot-widget");
    widget.classList.remove("is-bot", "is-human");
    document.getElementById("bot-score").textContent = "--;";
    document.getElementById("bot-bar").style.width = "0%";
    document.getElementById("bot-status").textContent = "--;";
}
