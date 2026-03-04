"""
Flask application factory and instance.

The create_app() function initializes the Flask application with proper
logging configuration. The app instance at module level is for production
WSGI servers (Gunicorn, Waitress, etc.).
"""
import os

from flask import Flask



class AppContext(Flask):
    pass


def create_app() -> Flask:
    """
    Create and configure the Flask application instance.

    Returns:
        Flask: Configured Flask application instance
    """

    # Create logs directory if needed
    os.makedirs("logs", exist_ok=True)

    # Create data directory if needed
    os.makedirs("data", exist_ok=True)

    app = Flask(__name__)

    # Instantiate services in app context
    with app.app_context():
        pass

    # Init pages routes
    from .routes import main as main_blueprint

    app.register_blueprint(main_blueprint)

    # Init ajax endpoints
    from .ajax import ajax as ajax_blueprint

    app.register_blueprint(ajax_blueprint, url_prefix="/ajax")

    return app


# Application instance for production WSGI servers
# Usage: gunicorn "app:app" or waitress-serve app:app
# If imported as a module, the app instance will be used by the server.
app = create_app()