"""
Central configuration for Professor Pepe.

All environment-specific values are loaded here so the rest of the codebase
does not depend on os.getenv scattered everywhere.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent.parent

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

IMAGE_API_BASE = os.getenv("IMAGE_API_BASE", "https://onlypepes.com").rstrip("/")
WATERMARK_PATH = os.getenv(
    "WATERMARK_PATH",
    str(BACKEND_DIR / "assets" / "watermark.png"),
)
MEMES_DIR = Path(os.getenv("MEMES_DIR", "")).expanduser() if os.getenv("MEMES_DIR") else None

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "professor_pepe")

SYSTEM_PROMPT_PATH = BACKEND_DIR / "persona" / "system_prompt.txt"

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
