"""Entry point for running the app (simplified).

This module no longer parses CLI flags; it simply creates the Flask app
and runs it on port 8000. Adjust `create_app()` or use a WSGI server
for production deployments.
"""

import os

from app import create_app


def main():
    app = create_app()
    # Read port and debug from environment so local dev and container runs match
    port = int(os.environ.get("PORT", "7860"))
    debug = os.environ.get("DEBUG", "1") in ("1", "true", "True")
    # Bind to 0.0.0.0 so the server is reachable from outside the container
    app.run(debug=debug, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
