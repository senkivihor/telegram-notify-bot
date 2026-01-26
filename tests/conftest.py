import os

# Ensure tests use an in-memory SQLite DB to avoid creating bot.db on disk.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Provide required location env vars so main.py can import without raising.
os.environ.setdefault("LOCATION_LAT", "00.000000")
os.environ.setdefault("LOCATION_LON", "00.000000")
os.environ.setdefault("LOCATION_VIDEO_URL", "https://example.com/entrance.mp4")
os.environ.setdefault(
    "LOCATION_SCHEDULE_TEXT",
    ("⏰ **Наш графік:**\n" "• Пн-Пт: 10:00 – 19:00\n" "• Сб: 11:00 – 14:00 (за дзвінком)\n" "• Нд: Вихідний"),
)
os.environ.setdefault("LOCATION_CONTACT_PHONE", "+380000000000")
