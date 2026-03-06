"""Entry point for running the app (simplified).

This module no longer parses CLI flags; it simply creates the Flask app
and runs it on port 8000. Adjust `create_app()` or use a WSGI server
for production deployments.
"""

import warnings
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
    # For now we only print status; run the server in dev to inspect
    app.run(debug=True, port=8000)


if __name__ == "__main__":
    main()
