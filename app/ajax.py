"""
AJAX endpoints

Only design here function designed to be called from
front end. No complex logic.
"""
from flask import Blueprint, render_template, jsonify, current_app, request

from typing import cast

from app import AppContext

# Cast app_context typing
app = cast(AppContext, current_app)
# Create blueprint
ajax = Blueprint("ajax", __name__)



# ------------- Render templates

@ajax.route('/render_categories')
def render_categories():
    """
    Render categories section

    Returns:
        HTML: Categories menu section
    """
    categories = app.product_data.get_available_categories()
    return render_template(
        "elements/categories.html",
        categories=categories
    )

@ajax.route('/render_products/')
def render_products():
    """
    Render product result

    Args:
        category (str): Product category
        page (int): Result page to render

    Returns:
        html: Product result section
    """
    category = request.args.get('category', 'all')
    page = request.args.get('page', 0, type=int)

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
        max_page=max_page
    )



# ------------- Tracking

@ajax.route('/track_inputs', methods=['POST'])
def track_inputs():
    stats = request.json
    print(stats)
    return jsonify({"success": True})