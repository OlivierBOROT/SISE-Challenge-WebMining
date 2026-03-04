"""
App routes

Only design here routes (pages) for the front end
"""
from flask import Blueprint, render_template


# Create blueprint
main = Blueprint("main", __name__)

@main.route('/')
def home():
    """
    Render the main page

    Returns:
        html: Main page HTML
    """
    return render_template(
        "index.html",
    )