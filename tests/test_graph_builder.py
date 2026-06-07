import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src.graph_builder import (
    build_ac_to_ac_graph,
    build_full_graph,
    find_connected_components,
    find_loops,
    compute_total_exposure,
)
from src.config import DATA_PATH


def test_build_ac_to_ac_graph():
    df = pd.read_csv(str(DATA_PATH))
    ac_df = df[df['counterparty_id'].str.startswith('AC-')]
    G = build_ac_to_ac_graph(ac_df)
    assert G.number_of_nodes() == 9
    assert G.number_of_edges() == 6


def test_build_full_graph():
    df = pd.read_csv(str(DATA_PATH))
    G = build_full_graph(df)
    assert G.number_of_nodes() == 497
    assert G.number_of_edges() == 4588


def test_find_connected_components():
    df = pd.read_csv(str(DATA_PATH))
    ac_df = df[df['counterparty_id'].str.startswith('AC-')]
    G = build_ac_to_ac_graph(ac_df)
    comps = find_connected_components(G)
    assert len(comps) >= 2


def test_find_loops():
    df = pd.read_csv(str(DATA_PATH))
    ac_df = df[df['counterparty_id'].str.startswith('AC-')]
    loops = find_loops(ac_df)
    assert len(loops) == 6
    for loop in loops:
        assert 'sender' in loop
        assert 'receiver' in loop
        assert 'txn_count' in loop
        assert 'total_amount' in loop


def test_total_exposure():
    df = pd.read_csv(str(DATA_PATH))
    ac_df = df[df['counterparty_id'].str.startswith('AC-')]
    loops = find_loops(ac_df)
    exposure = compute_total_exposure(loops)
    assert exposure == 161750.90


def test_loop_amounts():
    df = pd.read_csv(str(DATA_PATH))
    ac_df = df[df['counterparty_id'].str.startswith('AC-')]
    loops = find_loops(ac_df)
    for loop in loops:
        assert 24928.24 <= loop['total_amount'] <= 29120.71
        assert 41 <= loop['txn_count'] <= 42


def test_ring_account_ids():
    df = pd.read_csv(str(DATA_PATH))
    ac_df = df[df['counterparty_id'].str.startswith('AC-')]
    G = build_ac_to_ac_graph(ac_df)
    nodes = sorted(G.nodes())
    expected = ['AC-0001', 'AC-0002', 'AC-0003', 'AC-0005',
                'AC-0006', 'AC-0007', 'AC-0009', 'AC-0010', 'AC-0011']
    assert nodes == expected
