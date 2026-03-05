"""Entry point for running the app (simplified).

This module no longer parses CLI flags; it simply creates the Flask app
and runs it on port 8000. Adjust `create_app()` or use a WSGI server
for production deployments.
"""

from app import create_app


def main():
    app = create_app()
    app.run(port=8000)


if __name__ == "__main__":
    main()
