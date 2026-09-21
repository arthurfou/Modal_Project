"""Project configuration, read from environment variables (and the `.env` file if present)."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "rap_graph")

DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = PROJECT_ROOT / "graphs"

WORD2BEZBAR_REPO = "rapminerz/Word2Bezbar-large"


def require_env(name):
    """Return the value of an environment variable, or exit with a helpful message if it is missing."""
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing environment variable {name}. Copy .env.example to .env and fill it in.")
    return value
