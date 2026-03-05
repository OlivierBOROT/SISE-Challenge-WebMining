"""
App routes

Only design here routes (pages) for the front end
"""
from typing import cast

from flask import Blueprint, render_template, make_response, jsonify, current_app

from app import AppContext



app = cast(AppContext, current_app)
# Create blueprint
main = Blueprint("main", __name__)

@main.route('/')
def home():
    """
    Render the main page. Include session_id in response header

    Returns:
        html: Main page HTML
    """
    resp = make_response(render_template("index.html"))
    session = app.user_service.create_session()
    resp.set_cookie('session_id', session.id, httponly=False)
    resp.headers["X-Session-ID"] = session.id

    return resp

@main.route('/session/<session_id>')
def get_session(session: str):
    """
    Retrieve predictions for a specific session

    Args:
        session (str): Session ID to retrieve

    Returns:
        json: {
            predictions {
                is_bot: bool,
                bot_score: float.
                classe: str
            }
        }
    """
    return jsonify({'exemple': 1})