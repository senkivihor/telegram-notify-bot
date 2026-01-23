# Use a lightweight Python image
FROM python:3.10-slim

# Prevent Python from writing pyc files to disc and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy only dependency files first (caching layer)
COPY pyproject.toml poetry.lock ./

# Install dependencies
# We add "gunicorn" here explicitly in case it's not in your pyproject.toml
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root \
    && pip install gunicorn

# Copy the rest of the code
COPY . .

# EXPOSE the port (documentation only, but good practice)
EXPOSE 5000

# DEFAULT COMMAND
# This uses the PORT environment variable.
# On Render: Render sets $PORT automatically (e.g., 10000).
# Locally: It defaults to 5000.
CMD gunicorn --bind 0.0.0.0:${PORT:-5000} main:app
