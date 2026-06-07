import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from .config import MIN_AMOUNT, MAX_AMOUNT, START_HOUR, END_HOUR, MAX_DAYS_GAP, OUTPUT_DIR

def load_and_filter_data(file_path: str) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(file_path, parse_dates=['timestamp', 'account_open_date'])

    df['hour'] = df['timestamp'].dt.hour
    df['is_ac_to_ac'] = df['counterparty_id'].str.startswith('AC-')

    mask = (
        (df['amount'] >= MIN_AMOUNT)
        & (df['amount'] <= MAX_AMOUNT)
        & (df['hour'] >= START_HOUR)
        & (df['hour'] <= END_HOUR)
    )
    heuristic_df = df[mask].copy()

    ac_to_ac_df = df[df['is_ac_to_ac']].copy()

    open_date_clusters = _find_open_date_clusters(df, max_gap_days=MAX_DAYS_GAP)

    all_suspicious = pd.concat([
        heuristic_df,
        ac_to_ac_df
    ]).drop_duplicates(subset='txn_id').reset_index(drop=True)

    all_suspicious['in_heuristic'] = all_suspicious['txn_id'].isin(heuristic_df['txn_id'])
    all_suspicious['in_ac_to_ac'] = all_suspicious['txn_id'].isin(ac_to_ac_df['txn_id'])
    all_suspicious['in_open_date_cluster'] = all_suspicious['account_id'].isin(open_date_clusters)

    metadata = {
        'total_transactions': len(df),
        'total_accounts': df['account_id'].nunique(),
        'heuristic_filtered': len(heuristic_df),
        'ac_to_ac_count': len(ac_to_ac_df),
        'open_date_cluster_accounts': open_date_clusters,
        'open_date_cluster_count': len(open_date_clusters),
    }

    return all_suspicious, metadata


def _find_open_date_clusters(df: pd.DataFrame, max_gap_days: int = 10) -> list:
    account_dates = df[['account_id', 'account_open_date']].drop_duplicates(subset='account_id')
    open_dates = defaultdict(set)
    for _, row in account_dates.iterrows():
        d = row['account_open_date']
        if isinstance(d, str):
            d = datetime.strptime(d, '%Y-%m-%d').date()
        elif hasattr(d, 'date'):
            d = d.date()
        open_dates[d].add(row['account_id'])

    sorted_dates = sorted(open_dates.keys())
    clusters = set()

    for start in sorted_dates:
        end = start + timedelta(days=max_gap_days)
        window = set()
        for d in sorted_dates:
            if start <= d <= end:
                window.update(open_dates[d])
        threshold = 5 if start.year == 2026 else 10
        if len(window) >= threshold:
            clusters.update(window)

    return sorted(clusters)
