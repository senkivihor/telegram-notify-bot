import os

# Ensure tests use an in-memory SQLite DB to avoid creating bot.db on disk.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
