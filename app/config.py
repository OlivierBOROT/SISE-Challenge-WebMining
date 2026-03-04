"""
Application configuration.

Configuration is split by environment (Development, Testing, Production).
Environment variables override defaults.
"""
import os
from datetime import timedelta


class Config:
    """Base configuration - shared across all environments"""
    
    # Session & Security
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    
    # Bot Detection
    CAPTCHA_THRESHOLD = float(os.getenv("CAPTCHA_THRESHOLD", "0.65"))
    BATCH_WINDOW_SEC = int(os.getenv("BATCH_WINDOW_SEC", "5"))
    ROLLING_SCORE_ALPHA = float(os.getenv("ROLLING_SCORE_ALPHA", "0.7"))
    MAX_SESSION_DURATION_SEC = int(os.getenv("MAX_SESSION_DURATION_SEC", "1800"))
    
    # Model
    MODEL_HYPERPARAMS = {
        "n_estimators": 200,
        "contamination": 0.08,
        "contamination_random_state": 42,
    }


class DevelopmentConfig(Config):
    """Development environment"""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing environment"""
    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production environment"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


# Configuration selector
config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(env: str = None) -> type[Config]:
    """Get config class for environment"""
    if env is None:
        env = os.getenv("FLASK_ENV", "development")
    return config.get(env, config["default"])
