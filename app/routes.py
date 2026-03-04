"""
App routes

Only design here routes (pages) for the front end
"""

from flask import Blueprint, render_template, request, make_response


# Create blueprint
main = Blueprint("main", __name__)