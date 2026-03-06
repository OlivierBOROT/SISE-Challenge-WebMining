FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
ENV PORT=7860

# Install OS-level build dependencies required by some scientific packages
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		build-essential \
		gcc \
		g++ \
		gfortran \
		libopenblas-dev \
		liblapack-dev \
		git \
	&& rm -rf /var/lib/apt/lists/*

# Copy pyproject first to leverage Docker layer caching for deps
COPY pyproject.toml pyproject.toml

# Upgrade pip and install package (will install dependencies from pyproject)
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

EXPOSE 7860

# Default command — run the app with Gunicorn using the wsgi entrypoint
# Use the Python API config file `gunicorn_conf.py` for sensible defaults
CMD ["gunicorn", "wsgi:app", "-c", "gunicorn_conf.py"]

