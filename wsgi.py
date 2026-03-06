"""WSGI entrypoint for Gunicorn.

Expose a module-level ``app`` callable so Gunicorn can import it
with `gunicorn wsgi:app`.
"""

from app import create_app

app = create_app()
