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
    StorageService,
    FeatureService,
    TrainingService,
    DataConnector,
    BehaviorService,
)


class AppContext(Flask):
    """Flask app extended with service instances for dependency injection."""

    product_data: ProductData
    storage_service: StorageService
    feature_service: FeatureService
    training_service: TrainingService
    data_connector: DataConnector
    behavior_service: BehaviorService


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
        # Storage is foundational; other services depend on it
        app.storage_service = StorageService()  # type: ignore

        # Stateless services
        app.product_data = ProductData()  # type: ignore
        app.feature_service = FeatureService()  # type: ignore
        app.behavior_service = BehaviorService()  # type: ignore

        # Services that depend on storage
        app.training_service = TrainingService(storage=app.storage_service)  # type: ignore
        app.data_connector = DataConnector(storage=app.storage_service)  # type: ignore

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
