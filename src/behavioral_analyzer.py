import pandas as pd
import numpy as np
from collections import defaultdict
from datetime import timedelta
from src.config import DRIFT_DAYS


def analyze_all(df: pd.DataFrame) -> dict:
    signals = {
        'drift_candidates': _detect_behavioral_drift(df),
        'timing_regularity': _analyze_timing_regularity(df),
        'shared_devices': _find_shared_device_fingerprints(df),
        'ip_anomalies': _find_ip_region_anomalies(df),
        'account_summary': _summarize_accounts(df),
    }
    return signals


def _detect_behavioral_drift(df: pd.DataFrame, drift_days: int = DRIFT_DAYS) -> dict:
    df = df.sort_values(['account_id', 'timestamp']).copy()
    account_first = df.groupby('account_id')['timestamp'].min()

    fraud_accounts = set(df[df['counterparty_id'].str.startswith('AC-', na=False)]['account_id'])
    fraud_accounts.update(
        df[df['counterparty_id'].str.startswith('AC-', na=False)]['counterparty_id']
    )

    results = {}
    for acc_id in fraud_accounts:
        txns = df[df['account_id'] == acc_id].sort_values('timestamp')
        if len(txns) < 5:
            results[acc_id] = {'drift': False, 'reason': 'too_few_txns'}
            continue

        first_txn_time = txns['timestamp'].iloc[0]
        drift_threshold = first_txn_time + timedelta(days=drift_days)
        late_txns = txns[txns['timestamp'] >= drift_threshold]
        early_txns = txns[txns['timestamp'] < drift_threshold]

        if len(late_txns) == 0 or len(early_txns) == 0:
            results[acc_id] = {'drift': False, 'reason': 'no_split'}
            continue

        early_avg = early_txns['amount'].mean()
        late_avg = late_txns['amount'].mean()
        amount_change = abs(late_avg - early_avg) / max(early_avg, 1)

        early_not_ac = early_txns[~early_txns['counterparty_id'].str.startswith('AC-', na=False)]
        late_ac = late_txns[late_txns['counterparty_id'].str.startswith('AC-', na=False)]

        early_normal_fraction = len(early_not_ac) / max(len(early_txns), 1)
        late_ring_fraction = len(late_ac) / max(len(late_txns), 1)

        is_drift = (
            early_normal_fraction >= 0.5
            and late_ring_fraction >= 0.3
        ) or (
            amount_change > 2.0
            and late_ring_fraction > 0
        )

        results[acc_id] = {
            'drift': bool(is_drift),
            'early_normal_fraction': round(early_normal_fraction, 3),
            'late_ring_fraction': round(late_ring_fraction, 3),
            'amount_change_factor': round(amount_change, 2),
            'early_txn_count': len(early_txns),
            'late_txn_count': len(late_txns),
        }

    return results


def _analyze_timing_regularity(df: pd.DataFrame) -> dict:
    df = df.sort_values(['account_id', 'timestamp']).copy()

    fraud_accounts = set(df[df['counterparty_id'].str.startswith('AC-', na=False)]['account_id'])

    results = {}
    for acc_id in fraud_accounts:
        txns = df[df['account_id'] == acc_id].sort_values('timestamp')
        ac_txns = txns[txns['counterparty_id'].str.startswith('AC-', na=False)]

        if len(ac_txns) < 5:
            results[acc_id] = {
                'regular_intervals': False,
                'within_cluster_regular': False,
                'interval_std_seconds': None,
                'interval_mean_seconds': None,
                'cv': None,
            }
            continue

        ac_txns['date'] = ac_txns['timestamp'].dt.date
        within_cluster_intervals = []
        cluster_counts = []
        for _, cluster in ac_txns.groupby('date'):
            if len(cluster) >= 3:
                intervals = cluster['timestamp'].diff().dt.total_seconds().dropna()
                within_cluster_intervals.extend(intervals.tolist())
                cluster_counts.append(len(cluster))

        if within_cluster_intervals:
            wc_series = pd.Series(within_cluster_intervals)
            wc_mean = wc_series.mean()
            wc_std = wc_series.std()
            wc_cv = wc_std / wc_mean if wc_mean > 0 else float('inf')
            within_cluster_regular = bool(wc_cv < 0.5)
        else:
            within_cluster_regular = False
            wc_cv = None

        intervals = ac_txns['timestamp'].diff().dt.total_seconds().dropna()
        if len(intervals) < 3:
            results[acc_id] = {
                'regular_intervals': False,
                'within_cluster_regular': within_cluster_regular,
                'interval_std_seconds': None,
                'interval_mean_seconds': None,
                'cv': None,
                'within_cluster_cv': round(wc_cv, 3) if wc_cv is not None else None,
                'cluster_days': len(cluster_counts),
            }
            continue

        mean_sec = intervals.mean()
        std_sec = intervals.std()
        cv = std_sec / mean_sec if mean_sec > 0 else float('inf')
        is_regular = cv < 0.5

        results[acc_id] = {
            'regular_intervals': bool(is_regular),
            'within_cluster_regular': within_cluster_regular,
            'interval_std_seconds': round(std_sec, 1),
            'interval_mean_seconds': round(mean_sec, 1),
            'cv': round(cv, 3),
            'within_cluster_cv': round(wc_cv, 3) if wc_cv is not None else None,
            'cluster_days': len(cluster_counts),
        }

    return results


def _find_shared_device_fingerprints(df: pd.DataFrame) -> dict:
    device_accounts = defaultdict(set)
    for _, row in df.iterrows():
        device = row.get('device_id', '')
        if device:
            device_accounts[device].add(row['account_id'])

    shared = {}
    for device, accounts in device_accounts.items():
        if len(accounts) > 1:
            shared[device] = sorted(accounts)

    return {
        'shared_devices': shared,
        'count': len(shared),
    }


def _find_ip_region_anomalies(df: pd.DataFrame) -> dict:
    df = df.sort_values(['account_id', 'timestamp']).copy()

    fraud_accounts = set(df[df['counterparty_id'].str.startswith('AC-', na=False)]['account_id'])

    results = {}
    for acc_id in fraud_accounts:
        txns = df[df['account_id'] == acc_id].sort_values('timestamp')
        if 'ip_region' not in txns.columns:
            continue

        regions = txns['ip_region'].dropna().unique()
        if len(regions) > 2:
            results[acc_id] = {
                'region_changes': len(regions),
                'regions': list(regions),
            }
        elif len(txns) >= 10:
            region_counts = txns['ip_region'].value_counts()
            dominant = region_counts.index[0]
            minority_ratio = 1 - (region_counts.iloc[0] / len(txns))
            if minority_ratio > 0.3:
                results[acc_id] = {
                    'region_changes': len(regions),
                    'regions': list(regions),
                }

    return results


def _summarize_accounts(df: pd.DataFrame) -> dict:
    summary = {}
    for acc_id, group in df.groupby('account_id'):
        summary[acc_id] = {
            'total_txns': len(group),
            'total_amount': round(group['amount'].sum(), 2),
            'avg_amount': round(group['amount'].mean(), 2),
            'first_txn': str(group['timestamp'].min()),
            'last_txn': str(group['timestamp'].max()),
            'unique_ip_regions': group['ip_region'].nunique() if 'ip_region' in group else 0,
        }
    return summary
