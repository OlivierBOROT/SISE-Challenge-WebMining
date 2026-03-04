"""
Flask application factory and instance.

The create_app() function initializes the Flask application with proper
logging configuration. The app instance at module level is for production
WSGI servers (Gunicorn, Waitress, etc.).
"""
import os
from dotenv import load_dotenv

from flask import Flask

from app.config import get_config
from app.services.product_data import ProductData



class AppContext(Flask):
    product_data: ProductData


def create_app(config_name: str = None) -> Flask:
    """
    Create and configure the Flask application instance.

    Args:
        config_name: Environment config name (development, testing, production)
                     Defaults to FLASK_ENV env var or 'development'

    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)

    load_dotenv()
    
    # Load configuration
    app.config.from_object(get_config(config_name))

    # Instantiate services in app context
    with app.app_context():
        app.product_data = ProductData() #type: ignore

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