import multiprocessing

# Gunicorn configuration file. Values chosen to be sensible for small-to-medium
# containers; override in docker-compose or via CLI if needed.
workers = max(2, multiprocessing.cpu_count() * 2 + 1)
threads = 2
# Use port 7860 per request
bind = "0.0.0.0:7860"
timeout = 120

# Log to stdout/stderr so container logs capture them
capture_output = True
loglevel = "info"
