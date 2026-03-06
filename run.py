"""Entry point for running the app (simplified).

This module no longer parses CLI flags; it simply creates the Flask app
and runs it on port 7860. Adjust `create_app()` or use a WSGI server
for production deployments.
"""

import warnings
import os
# sklearn ≥ 1.3 warns when its internal joblib.delayed is used without
# sklearn's own Parallel wrapper — this is a sklearn internals issue, not ours.
warnings.filterwarnings(
    "ignore",
    message=r"`sklearn\.utils\.parallel\.delayed` should be used",
    category=UserWarning,
    module=r"sklearn\.utils\.parallel",
)

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
