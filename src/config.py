import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_PATH = PROJECT_ROOT / "data" / "track02_fraud_watch.csv"
OUTPUT_DIR = PROJECT_ROOT / "results"

MIN_AMOUNT = 400
MAX_AMOUNT = 900
START_HOUR = 2
END_HOUR = 4

USE_LLM = os.getenv("USE_LLM", "false").lower() in ("true", "1", "yes")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "")

ANSWER_KEY_PATH = os.getenv("ANSWER_KEY_PATH", PROJECT_ROOT / "answer_key.json")

DRIFT_DAYS = 60
MAX_DAYS_GAP = 10
CYCLE_MIN_LENGTH = 3
SHARED_DEVICE_WEIGHT = 1.5
DRIFT_WEIGHT = 2.0
OPEN_DATE_WEIGHT = 2.0
TIMING_REGULARITY_WEIGHT = 1.5
SCC_WEIGHT = 3.0
DISTRACTOR_PENALTY = 2.0
RING_THRESHOLD = 4.0
