export function setBotResult(label, score, confidence, persona) {
    const widget = document.getElementById("bot-widget");
    const elScore = document.getElementById("bot-score");
    const elBar = document.getElementById("bot-bar");
    const elStatus = document.getElementById("bot-status");
    const elVerdict = document.getElementById("bot-verdict");

    widget.classList.remove("is-bot", "is-human");

    elScore.textContent = score.toFixed(2);
    elBar.style.width = (score * 100) + "%";

    const personaLabel = persona && persona !== "human" && persona !== "bot"
        ? ` (${persona.replace("bot_", "")} pattern)`
        : "";

    if (label === "bot") {
        widget.classList.add("is-bot");
        elStatus.textContent = "⚠ Bot";
        elVerdict.textContent = `Classified as BOT${personaLabel} — ${(confidence * 100).toFixed(0)}% confidence`;
    } else {
        widget.classList.add("is-human");
        elStatus.textContent = "✓ Human";
        elVerdict.textContent = confidence >= 0.75
            ? "Classified as Human — high confidence"
            : "Classified as Human — low confidence";
    }
}

export function clearBotResult() {
    const widget = document.getElementById("bot-widget");
    widget.classList.remove("is-bot", "is-human");
    document.getElementById("bot-score").textContent = "--;";
    document.getElementById("bot-bar").style.width = "0%";
    document.getElementById("bot-status").textContent = "--;";
}
