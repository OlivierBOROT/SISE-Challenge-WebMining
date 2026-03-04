"""
AJAX endpoints

Only design here function designed to be called from
front end. No complex logic.
"""
from typing import cast

from flask import Blueprint, abort, current_app, jsonify, render_template, request

from app import AppContext

# Cast app_context typing
app = cast(AppContext, current_app)
# Create blueprint
ajax = Blueprint("ajax", __name__)


