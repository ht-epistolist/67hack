"""Central configuration for the frtc backend.

Reads from environment / a local .env file. The only required secret is
OPENROUTER_API_KEY; everything else has a sensible default.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

# Load backend/.env if present.
load_dotenv(BACKEND_DIR / ".env")


class Settings:
    # --- Data ---
    csv_path: Path = Path(
        os.getenv("FRAUD_CSV_PATH", REPO_ROOT / "data" / "track02_fraud_watch.csv")
    )

    # --- OpenRouter (agents) ---
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    # Google Vertex (Gemini) models, routed through the user's OpenRouter
    # account where their Vertex integration key is enabled.
    agent_model: str = os.getenv("AGENT_MODEL", "google/gemini-2.5-flash")
    reasoning_model: str = os.getenv("REASONING_MODEL", "google/gemini-2.5-pro")

    # --- Cognee memory ---
    cognee_dir: Path = BACKEND_DIR / ".cognee"
    cognee_llm_model: str = os.getenv(
        "COGNEE_LLM_MODEL", "openrouter/google/gemini-2.5-flash"
    )
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "384"))
    cognee_max_edges: int = int(os.getenv("COGNEE_MAX_EDGES", "0"))

    # Toggle: if Cognee fails to init (e.g. no model access), the system still
    # runs with an in-process memory fallback so the demo never hard-crashes.
    use_cognee: bool = os.getenv("USE_COGNEE", "1") not in ("0", "false", "False")

    @property
    def has_llm(self) -> bool:
        return bool(self.openrouter_api_key)


settings = Settings()
