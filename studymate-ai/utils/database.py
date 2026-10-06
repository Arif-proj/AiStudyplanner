"""Reusable MongoDB connection (PyMongo + MongoDB Atlas)."""
from pymongo import MongoClient, ASCENDING

import config

_client = None


def get_client():
    """Create the MongoClient once and reuse it."""
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db():
    """Return the application database."""
    return get_client()[config.DATABASE_NAME]


def check_connection():
    """Ping MongoDB at start-up. Prints a friendly message, never the password."""
    try:
        get_client().admin.command("ping")
        print("✅ MongoDB Connected")
        return True
    except Exception:
        print("❌ MongoDB connection failed. Check MONGO_URI in your .env file "
              "and your Atlas network access (IP allow-list).")
        return False


def create_indexes():
    """Unique email + helpful lookup indexes."""
    db = get_db()
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.subjects.create_index("user_id")
    db.topics.create_index([("user_id", ASCENDING), ("subject_id", ASCENDING)])
    db.study_tasks.create_index([("user_id", ASCENDING), ("study_date", ASCENDING)])
    db.study_sessions.create_index("user_id")
