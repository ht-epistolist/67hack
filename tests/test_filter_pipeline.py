import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src.config import DATA_PATH
from src.filter_pipeline import load_and_filter_data, _find_open_date_clusters


def test_load_and_filter_data():
    filtered_df, metadata = load_and_filter_data(str(DATA_PATH))
    assert filtered_df is not None
    assert metadata is not None
    assert metadata['total_transactions'] == 5000
    assert metadata['total_accounts'] == 294


def test_heuristic_filter():
    filtered_df, metadata = load_and_filter_data(str(DATA_PATH))
    heuristic = filtered_df[filtered_df['in_heuristic']]
    assert len(heuristic) > 0
    assert heuristic['amount'].between(400, 900).all()
    assert heuristic['hour'].between(2, 4).all()


def test_ac_to_ac_filter():
    filtered_df, metadata = load_and_filter_data(str(DATA_PATH))
    ac_to_ac = filtered_df[filtered_df['in_ac_to_ac']]
    assert len(ac_to_ac) == 250
    assert ac_to_ac['counterparty_id'].str.startswith('AC-').all()


def test_open_date_clusters():
    df = pd.read_csv(str(DATA_PATH), parse_dates=['account_open_date'])
    clusters = _find_open_date_clusters(df)
    assert isinstance(clusters, list)
    assert len(clusters) >= 6


def test_metadata_fields():
    _, metadata = load_and_filter_data(str(DATA_PATH))
    expected_keys = [
        'total_transactions', 'total_accounts',
        'heuristic_filtered', 'ac_to_ac_count',
        'open_date_cluster_accounts', 'open_date_cluster_count'
    ]
    for key in expected_keys:
        assert key in metadata, f"Missing metadata key: {key}"
