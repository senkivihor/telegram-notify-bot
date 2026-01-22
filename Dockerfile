# 1. Base Image (Lightweight Python)
FROM python:3.11-slim

# 2. Environment Variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false

# Add Poetry to PATH
ENV PATH="$POETRY_HOME/bin:$PATH"

# 3. Install System Dependencies
# 'curl' is for installing Poetry
# 'libpq-dev' and 'gcc' are required for PostgreSQL adapter (psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 4. Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# 5. Set Working Directory
WORKDIR /app

# 6. Install Python Dependencies
# We copy ONLY the dependency files first. Docker caches this layer.
# If you change code but not dependencies, this step is skipped (Builds are faster).
COPY pyproject.toml poetry.lock ./

# --no-root: Do not install the project itself yet
# --only main: Do not install 'pytest' (keep production image small)
RUN poetry install --no-root --only main

# 7. Copy the rest of the Application Code
COPY . .

# 8. Security: Run as non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# 9. Expose the Flask port
EXPOSE 5000

# 10. Start the App using Gunicorn (Production Server)
# "main:app" means: look in main.py for the object named 'app'
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "main:app"]
