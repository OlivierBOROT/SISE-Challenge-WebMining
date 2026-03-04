"""
AJAX endpoints

Only design here function designed to be called from
front end. No complex logic.
"""

from typing import cast

from flask import Blueprint, current_app, jsonify, request

from app import AppContext
from app.bot_detector import detect as detect_bot

# Cast app_context typing
app = cast(AppContext, current_app)
# Create blueprint
ajax = Blueprint("ajax", __name__)

# In-memory store (per-server process) – fine for a demo
_mouse_logs: list[dict] = []


@ajax.route("/mouse", methods=["POST"])
def receive_mouse_data():
    """Receive a batch of mouse events from the browser."""
    payload = request.get_json(silent=True)
    if not payload or "events" not in payload:
        return jsonify({"status": "error", "msg": "no events"}), 400

    events = payload["events"]
    _mouse_logs.extend(events)
    return jsonify({"status": "ok", "stored": len(_mouse_logs)})


@ajax.route("/mouse", methods=["GET"])
def get_mouse_data():
    """Return all stored mouse events (for debug / analysis)."""
    return jsonify({"events": _mouse_logs, "total": len(_mouse_logs)})


@ajax.route("/detect", methods=["POST"])
def bot_detect():
    """
    Receive computed mouse features from the front-end and run
    Isolation Forest bot detection.

    Expected JSON body: { "features": { "speed_avg": ..., ... } }
    """
    payload = request.get_json(silent=True)
    if not payload or "features" not in payload:
        return jsonify({"status": "error", "msg": "no features"}), 400

    result = detect_bot(payload["features"])
    return jsonify({"status": "ok", **result})
