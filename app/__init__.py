"""
Flask application factory and instance.

The create_app() function initializes the Flask application with proper
logging configuration. The app instance at module level is for production
WSGI servers (Gunicorn, Waitress, etc.).
"""

from dotenv import load_dotenv
from flask import Flask

from app.services import (
    ProductData,
    UserService,
)


class AppContext(Flask):
    """Flask app extended with service instances for dependency injection."""

    product_data: ProductData
    user_service: UserService


def create_app() -> Flask:
    """
    Create and configure the Flask application instance.

    Initializes all service instances with explicit dependency injection.
    Services are instantiated once per app instance and managed by Flask context.

    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)

    load_dotenv()

    # Instantiate services with explicit dependency injection
    with app.app_context():
        app.debug = False
        app.product_data = ProductData()  # type: ignore
        app.user_service = UserService()  # type: ignore

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
