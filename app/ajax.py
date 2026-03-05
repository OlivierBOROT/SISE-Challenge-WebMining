"""
AJAX endpoints

Only design here function designed to be called from
front end. No complex logic.
"""

import time
from typing import cast

from flask import Blueprint, current_app, jsonify, render_template, request

from app import AppContext
from app.behavior_model import FeatureBuilder
from app.schemas import MouseBehaviorBatch, UserEvents

# Cast app_context typing
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
    page = request.args.get("page", 0, type=int)

    if category == "all":
        products = app.product_data.get_all()
    else:
        products = app.product_data.get_by_category(category)

    products, max_page = app.product_data.paginate(products, page)

    return render_template(
        "elements/products.html",
        category=category,
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
        json: client input metrics

    Returns:
        json: {
            "is_bot": bool
            "bot_score": int
        }
    """
    stats = request.json
    behaviour_batch = MouseBehaviorBatch(**stats)

    feature_set = app.feature_service.extract(behaviour_batch)
    # Always store incoming input-derived features to main storage
    app.storage_service.append(feature_set)

    return jsonify({"success": True})


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
    data = request.json
    user_events = UserEvents(**data)

    # Convert Pydantic models to plain dicts for FeatureBuilder
    events_dicts = [e.model_dump() for e in user_events.events]

    result = app.behavior_service.predict_from_raw(
        events_dicts, session_id=user_events.user_id
    )
    fs = result.get("feature_set")
    if fs is not None:
        app.storage_service.append(fs)
    return jsonify(
        {
            "user_id": user_events.user_id,
            "features": result.get("features"),
            "label": result.get("label"),
        }
    )
