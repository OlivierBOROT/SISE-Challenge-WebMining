"""
AJAX endpoints

Only design here function designed to be called from
front end. No complex logic.
"""

from typing import cast

from flask import Blueprint, current_app, jsonify, render_template, request

from app import AppContext
from app.schemas import MouseBehaviorBatch

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
    app = cast(AppContext, current_app)
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
    app = cast(AppContext, current_app)
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
    app = cast(AppContext, current_app)
    stats = request.json
    behaviour_batch = MouseBehaviorBatch(**stats)

    feature_set = app.feature_service.extract(behaviour_batch)
    app.storage_service.append(feature_set)
    
    return jsonify({"success": True})
