"""Loads a transaction CSV into a pandas DataFrame with the derived columns the
analytics tools rely on. The *active* dataset is swappable at runtime (so the UI
can select / upload datasets); tools always read through `get_data()`.
"""
from __future__ import annotations

import pandas as pd

from app.config import settings

REQUIRED_COLUMNS = {
    "txn_id",
    "account_id",
    "counterparty_id",
    "amount",
    "timestamp",
    "merchant_category",
    "device_id",
    "ip_region",
    "account_open_date",
}


class SchemaError(ValueError):
    """Raised when an uploaded/selected CSV is missing required columns."""


class FraudData:
    """Parsed transaction dataset + cheap shared accessors."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.window_start: pd.Timestamp = df["timestamp"].min()
        self.window_end: pd.Timestamp = df["timestamp"].max()

    # ------------------------------------------------------------------ #
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "FraudData":
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise SchemaError(
                "CSV is missing required column(s): " + ", ".join(sorted(missing))
            )
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["account_open_date"] = pd.to_datetime(df["account_open_date"])
        df["hour"] = df["timestamp"].dt.hour
        df["date"] = df["timestamp"].dt.date
        # Account-to-account transfer = counterparty is itself a bank account
        # (AC-####) rather than a merchant (MR-####).
        df["is_a2a"] = df["counterparty_id"].astype(str).str.startswith("AC-")
        window_start = df["timestamp"].min()
        df["account_age_days"] = (window_start - df["account_open_date"]).dt.days
        return cls(df)

    @classmethod
    def from_csv(cls, path) -> "FraudData":
        return cls.from_dataframe(pd.read_csv(path))

    # ------------------------------------------------------------------ #
    @property
    def accounts(self) -> list[str]:
        return sorted(self.df["account_id"].unique().tolist())

    @property
    def all_account_ids(self) -> set[str]:
        senders = set(self.df["account_id"].unique())
        receivers = set(self.df.loc[self.df["is_a2a"], "counterparty_id"].unique())
        return senders | receivers

    def account_txns(self, account_id: str) -> pd.DataFrame:
        return self.df[self.df["account_id"] == account_id]

    def open_date(self, account_id: str):
        rows = self.account_txns(account_id)
        if len(rows):
            return rows["account_open_date"].iloc[0]
        return None

    def summary(self) -> dict:
        return {
            "transactions": int(len(self.df)),
            "originating_accounts": len(self.accounts),
            "total_accounts_seen": len(self.all_account_ids),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "window_days": int((self.window_end - self.window_start).days),
            "a2a_transactions": int(self.df["is_a2a"].sum()),
            "merchant_categories": sorted(self.df["merchant_category"].unique().tolist()),
            "ip_regions": sorted(self.df["ip_region"].unique().tolist()),
        }


# --------------------------- active dataset ------------------------------- #
_active_path: str | None = None
_cache: dict[str, FraudData] = {}


def load_dataset(path) -> FraudData:
    """Parse a CSV (validated, cached by path). Raises SchemaError on bad files."""
    key = str(path)
    if key not in _cache:
        _cache[key] = FraudData.from_csv(key)
    return _cache[key]


def set_active_dataset(path) -> FraudData:
    """Switch the active dataset (validates + warms the cache)."""
    global _active_path
    data = load_dataset(path)  # validate before committing
    _active_path = str(path)
    return data


def active_path() -> str:
    global _active_path
    if _active_path is None:
        _active_path = str(settings.csv_path)
    return _active_path


def get_data() -> FraudData:
    """The currently-active parsed dataset (defaults to the bundled CSV)."""
    return load_dataset(active_path())
