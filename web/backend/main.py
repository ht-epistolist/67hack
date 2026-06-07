import json
import subprocess
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from src.config import (
    MIN_AMOUNT, MAX_AMOUNT, START_HOUR, END_HOUR, MAX_DAYS_GAP,
    CYCLE_MIN_LENGTH, DRIFT_DAYS, DRIFT_WEIGHT, TIMING_REGULARITY_WEIGHT,
    SHARED_DEVICE_WEIGHT, DISTRACTOR_PENALTY, RING_THRESHOLD, SCC_WEIGHT,
    OPEN_DATE_WEIGHT,
)

app = FastAPI(title="Fraud Watch Detection Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_PATH = PROJECT_ROOT / "results" / "detection_result.json"
FRONTEND_PATH = PROJECT_ROOT / "web" / "frontend" / "public"
MAIN_PY = PROJECT_ROOT / "main.py"


@app.get("/api/results")
async def get_results():
    if not RESULTS_PATH.exists():
        try:
            subprocess.run(
                [sys.executable, str(MAIN_PY)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return {"error": "Pipeline timed out after 300s."}
        except Exception as e:
            return {"error": f"Pipeline failed: {e}"}

    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            return json.load(f)

    return {"error": "Pipeline did not produce results."}


@app.get("/api/refresh")
async def refresh_results():
    if RESULTS_PATH.exists():
        RESULTS_PATH.unlink()
    try:
        result = subprocess.run(
            [sys.executable, str(MAIN_PY)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            return {"error": f"Pipeline failed:\n{result.stderr}"}
    except subprocess.TimeoutExpired:
        return {"error": "Pipeline timed out after 300s."}
    except Exception as e:
        return {"error": f"Pipeline error: {e}"}

    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return {"error": "Pipeline did not produce results."}


@app.get("/api/algorithm")
async def get_algorithm():
    return {
        "stages": [
            {
                "stage": 1,
                "title": "Filter Suspicious Transactions",
                "description": "Load the raw CSV and apply three parallel filters to identify potentially fraudulent transactions.",
                "steps": [
                    {
                        "name": "Heuristic Filter",
                        "detail": f"Selects transactions where amount is between ${MIN_AMOUNT} and ${MAX_AMOUNT} and timestamp hour is between {START_HOUR}:00 and {END_HOUR}:00 (off-hours). This targets small, off-hour transfers typical of money laundering.",
                        "scope": "transaction-level"
                    },
                    {
                        "name": "AC-to-AC Filter",
                        "detail": "Selects all transactions where the counterparty_id starts with 'AC-', meaning the money moved between two accounts at the same bank. This is a strong signal because circular laundering requires internal transfers.",
                        "scope": "transaction-level"
                    },
                    {
                        "name": "Open Date Clustering",
                        "detail": f"Groups accounts by their account_open_date within {MAX_DAYS_GAP}-day sliding windows. If {MAX_DAYS_GAP} or more accounts (5 for 2026) opened in the same window, all are flagged. Fraud rings often open accounts in batches.",
                        "scope": "account-level"
                    }
                ]
            },
            {
                "stage": 2,
                "title": "Build Transaction Network & Find Loops",
                "description": "Construct a directed graph of AC-to-AC transactions and identify circular money flows.",
                "steps": [
                    {
                        "name": "Build AC-to-AC Graph",
                        "detail": "Create a NetworkX DiGraph from all AC-to-AC transactions. Each edge stores total_amount, txn_count, and avg_amount. Nodes are bank accounts.",
                        "scope": "graph"
                    },
                    {
                        "name": "Find Connected Components",
                        "detail": f"Extract weakly connected components with at least {CYCLE_MIN_LENGTH} nodes ({CYCLE_MIN_LENGTH}+ accounts). These strongly-connected subgraphs are suspect fraud rings operating together.",
                        "scope": "graph"
                    },
                    {
                        "name": "Find Circular Loops",
                        "detail": "Group AC-to-AC transactions by (sender, receiver) pairs and aggregate amounts. Each unique sender→receiver pair is a loop. Loops represent directional money flows within the ring.",
                        "scope": "graph"
                    },
                    {
                        "name": "Compute Total Exposure",
                        "detail": "Sum the total_amount across all detected loops to quantify the total dollar value flowing through the fraud network.",
                        "scope": "graph"
                    }
                ]
            },
            {
                "stage": 3,
                "title": "Analyze Behavioral Signals",
                "description": "Analyze transaction history for each account to detect patterns consistent with automated laundering.",
                "steps": [
                    {
                        "name": "Behavioral Drift",
                        "detail": f"Split each account's transactions at the {DRIFT_DAYS}-day mark from their first transaction. Flag accounts where early activity targets normal counterparties (>=50%) but later activity shifts to AC accounts (>=30%), OR where average amount changes by >2x and late AC activity exists. This detects accounts that started legitimately then turned fraudulent.",
                        "scope": "account-level",
                        "weight": DRIFT_WEIGHT
                    },
                    {
                        "name": "Timing Regularity",
                        "detail": "Group AC-to-AC transactions by date. Within clusters of >=3 same-day transactions, compute the coefficient of variation (CV) of intervals. CV < 0.5 indicates automated/scripted timing. Regular intervals suggest a bot rather than human behavior.",
                        "scope": "account-level",
                        "weight": TIMING_REGULARITY_WEIGHT
                    },
                    {
                        "name": "Shared Device Fingerprints",
                        "detail": "Group transactions by device_id. If a single device is used by multiple accounts, flag all associated accounts. Shared devices indicate a single operator controlling multiple ring accounts.",
                        "scope": "account-level",
                        "weight": SHARED_DEVICE_WEIGHT
                    },
                    {
                        "name": "IP Region Anomalies",
                        "detail": "For each account, count unique ip_region values. Flag if >2 regions appear, or if >=10 transactions with a minority region ratio >0.3. Unusual geographic spread suggests coordinated operation.",
                        "scope": "account-level"
                    }
                ]
            },
            {
                "stage": 4,
                "title": "Risk Scoring & Classification",
                "description": "Score every candidate account by summing weighted signals, then classify into risk tiers.",
                "steps": [
                    {
                        "name": "Accumulate Signal Weights",
                        "detail": "Each account starts at 0.0. Signals detected in earlier stages add to the score. The complete scoring table is shown below.",
                        "scope": "scoring"
                    },
                    {
                        "name": "Apply Distractor Penalty",
                        "detail": f"Accounts that are NOT in any loop but have IP anomalies or high avg transaction amounts (>$500) receive a -{DISTRACTOR_PENALTY} penalty. This prevents false positives from high-volume but legitimate accounts.",
                        "scope": "scoring",
                        "weight": -DISTRACTOR_PENALTY
                    },
                    {
                        "name": "Classify Accounts",
                        "detail": f"Accounts are classified into three tiers: Ring Member (score >= {RING_THRESHOLD}), Candidate (2.0 <= score < {RING_THRESHOLD}), or Exonerated (flagged as likely distractor during adjudication, capped at 20). Only Ring Members and Candidates are investigated; Exonerated accounts are removed from ring_members output.",
                        "scope": "scoring"
                    }
                ],
                "signals": [
                    {"name": "SCC Membership", "weight": SCC_WEIGHT, "description": "Account belongs to a strongly connected component of >=3 AC-to-AC nodes"},
                    {"name": "In Circular Loop", "weight": 3.0, "description": "Account appears as sender or receiver in any detected loop"},
                    {"name": "AC-to-AC Sender", "weight": 1.0, "description": "Account sent money to another AC- account"},
                    {"name": "Open Date Cluster", "weight": OPEN_DATE_WEIGHT, "description": "Account was opened within 10 days of other suspicious accounts"},
                    {"name": "Ring Member (partial)", "weight": f"{OPEN_DATE_WEIGHT * 0.5}", "description": "Account is in a loop but NOT in an open-date cluster (half weight)"},
                    {"name": "Heuristic Match", "weight": 1.0, "description": "Account had transactions matching the amount ($400-$900) and hour (2-4 AM) heuristic"},
                    {"name": "Behavioral Drift", "weight": DRIFT_WEIGHT, "description": "Account showed significant behavioral change after 60 days"},
                    {"name": "Regular Timing", "weight": TIMING_REGULARITY_WEIGHT, "description": "Account has automated/scripted transaction timing (CV < 0.5)"},
                    {"name": "Shared Device", "weight": SHARED_DEVICE_WEIGHT, "description": "Account shares a device fingerprint with another account"},
                    {"name": "Distractor Penalty", "weight": f"-{DISTRACTOR_PENALTY}", "description": "Account is not in a loop but has IP anomalies or high avg amount (>$500)"}
                ],
                "thresholds": {
                    "ring_member": {"min_score": RING_THRESHOLD, "label": "Ring Member", "color": "red"},
                    "candidate": {"min_score": 2.0, "max_score": RING_THRESHOLD, "label": "Candidate", "color": "yellow"},
                    "exonerated": {"label": "Exonerated", "color": "green", "description": "Flagged as likely false positive during adjudication"}
                }
            }
        ]
    }


@app.get("/api/transactions")
async def get_transactions():
    csv_path = PROJECT_ROOT / "data" / "track02_fraud_watch.csv"
    if csv_path.exists():
        import csv
        rows = []
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return {"transactions": rows}
    return {"error": "Data file not found."}


@app.get("/")
@app.get("/{path:path}")
async def serve_frontend(path: str = ""):
    index_path = FRONTEND_PATH / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Frontend not found."}
