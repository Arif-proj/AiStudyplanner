"""Configuration: every secret is read from the .env file (never hard-coded)."""
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "")
DATABASE_NAME = os.getenv("DATABASE_NAME", "studymate_ai")

# If SECRET_KEY is missing we create a temporary one so the app still starts.
# (Users will be logged out whenever the server restarts.)
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
