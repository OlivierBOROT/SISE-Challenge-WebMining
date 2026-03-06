import multiprocessing
import os

# Gunicorn configuration file. Read the port from the environment so the
# container can be started on any port (Hugging Face Spaces exposes PORT).
PORT = int(os.environ.get("PORT", "7860"))

# Workers/threads tuned reasonably for small-to-medium containers; override
# via GUNICORN_CMD_ARGS or by editing this file in the Space repository.
workers = 8
threads = 2
bind = f"0.0.0.0:{PORT}"
timeout = 120

# Log to stdout/stderr so container logs capture them
capture_output = True
loglevel = "info"
