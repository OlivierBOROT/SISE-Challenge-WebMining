"""
AJAX endpoints

Only design here function designed to be called from
front end. No complex logic.
"""
from typing import cast

from flask import Blueprint, current_app, jsonify, render_template, request

from app import AppContext

# Use BehaviorService via app.behavior_service (do not import FeatureBuilder here)
from app.schemas import MouseBehaviorBatch, UserEvents

app = cast(AppContext, current_app)
# Create blueprint
ajax = Blueprint("ajax", __name__)


# ------------- Render templates


@ajax.route("/render_categories")
def render_categories():
    """
    Render categories section

    Returns:
        HTML: Categories menu section
    """
    categories = app.product_data.get_available_categories()
    return render_template("elements/categories.html", categories=categories)


@ajax.route("/render_products/")
def render_products():
    """
    Render product result

    Args:
        category (str): Product category
        page (int): Result page to render

    Returns:
        html: Product result section
    """
    category = request.args.get("category", "all")
    query = request.args.get("query")
    page = request.args.get("page", 0, type=int)

    if query:
        products = app.product_data.search(query)
    elif category == "all":
        products = app.product_data.get_all()
    else:
        products = app.product_data.get_by_category(category)

    products, max_page = app.product_data.paginate(products, page)

    return render_template(
        "elements/products.html",
        category=category,
        query=query,
        products=products,
        page=page,
        max_page=max_page,
    )


# ------------- Tracking


@ajax.route("/track_inputs", methods=["POST"])
def track_inputs():
    """
    Predict bot / user label from client inputs

    Arguments:
        json: {
            "session_id": session id
            "stats": client input metrics
        }

    Returns:
        json: {
            "is_bot": bool
            "bot_score": int
        }
    """
    data = request.get_json(force=True)
    session_id: str = data.get("session_id")
    stats: dict = data.get("stats")
    source: str = stats.pop('_source', "human")

    behaviour_batch = MouseBehaviorBatch(**stats)
    result = app.user_service.predict_bot(behaviour_batch, session_id, source)

    return jsonify({
        "label": result.label,
        "score": result.score
    })


@ajax.route("/track_events", methods=["POST"])
def track_events():
    """
    Receive user interaction events (product, category, page) from
    the EventTracker JS module and build features via FeatureBuilder.

    Arguments:
        json: UserEvents payload { user_id, events[] }

    Returns:
        json: { features: dict, user_id: str }
    """
    data = request.get_json(force=True)
    session_id: str = data.get("session_id")
    events: dict = data.get("events")
    source: str = events.pop('_source', "human")

    user_events = UserEvents(**events)
    result = app.user_service.predict_behaviour(user_events, session_id, source)

    if not result:
        return jsonify({
            "warning": "Not enough data to run a predict. 10 seconds required"
        })

    return jsonify({
        "label": result.label,
        "projection": {
            "PC1": result.pc1,
            "PC2": result.pc2
        }
    })
