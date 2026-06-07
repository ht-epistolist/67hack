import networkx as nx
import pandas as pd
import json
from collections import defaultdict

from src.config import CYCLE_MIN_LENGTH


def build_ac_to_ac_graph(df: pd.DataFrame) -> nx.DiGraph:
    G = nx.DiGraph()
    ac_df = df[df['counterparty_id'].str.startswith('AC-')]

    for (src, dst), group in ac_df.groupby(['account_id', 'counterparty_id']):
        G.add_edge(src, dst, txns=group.to_dict('records'),
                   total_amount=group['amount'].sum(),
                   txn_count=len(group),
                   avg_amount=group['amount'].mean())
    return G


def build_full_graph(df: pd.DataFrame) -> nx.DiGraph:
    G = nx.DiGraph()
    for _, row in df.iterrows():
        attrs = {
            'amount': row['amount'],
            'timestamp': str(row['timestamp']),
        }
        if 'device_id' in row:
            attrs['device'] = row['device_id']
        if 'merchant_category' in row:
            attrs['category'] = row['merchant_category']
        if 'ip_region' in row:
            attrs['ip_region'] = row['ip_region']
        G.add_edge(row['account_id'], row['counterparty_id'], **attrs)
    return G


def find_connected_components(G: nx.DiGraph) -> list:
    wccs = list(nx.weakly_connected_components(G))
    nontrivial = [wcc for wcc in wccs if len(wcc) >= CYCLE_MIN_LENGTH]
    return nontrivial


def find_loops(ac_df: pd.DataFrame) -> list:
    pairs = ac_df.groupby(['account_id', 'counterparty_id']).agg(
        txn_count=('amount', 'count'),
        total_amount=('amount', 'sum'),
        avg_amount=('amount', 'mean'),
        min_amount=('amount', 'min'),
        max_amount=('amount', 'max'),
    ).reset_index()

    loops = []
    for _, p in pairs.iterrows():
        loops.append({
            'sender': p['account_id'],
            'receiver': p['counterparty_id'],
            'txn_count': int(p['txn_count']),
            'total_amount': round(float(p['total_amount']), 2),
            'avg_amount': round(float(p['avg_amount']), 2),
            'min_amount': round(float(p['min_amount']), 2),
            'max_amount': round(float(p['max_amount']), 2),
        })

    return loops


def compute_total_exposure(loops: list) -> float:
    return round(sum(l['total_amount'] for l in loops), 2)


def get_subgraph(G: nx.DiGraph, nodes: set) -> nx.DiGraph:
    return G.subgraph(nodes).copy()


class CogneeGraph:
    def __init__(self):
        self.initialized = False

    async def ingest(self, df: pd.DataFrame, dataset_name: str = "fraud_watch"):
        import cognee

        await cognee.prune.prune_data()

        data_items = []
        for _, row in df.iterrows():
            item = json.dumps({
                'txn_id': row['txn_id'],
                'account_id': row['account_id'],
                'counterparty_id': row['counterparty_id'],
                'amount': float(row['amount']),
                'timestamp': str(row['timestamp']),
                'merchant_category': row.get('merchant_category', ''),
                'device_id': row.get('device_id', ''),
                'ip_region': row.get('ip_region', ''),
                'account_open_date': str(row.get('account_open_date', '')),
            })
            data_items.append(item)

        import os
        if not os.getenv("OPENAI_API_KEY") and not os.getenv("LLM_API_KEY"):
            print("  Skipping Cognee cognify (no LLM API key configured)")
            self.initialized = True
            return

        await cognee.add(data_items, dataset_name=dataset_name)
        await cognee.cognify(datasets=[dataset_name])

        self.initialized = True

    async def search(self, query: str, top_k: int = 20):
        import cognee

        results = await cognee.search(query, top_k=top_k)
        return results

    async def recall(self, query: str, top_k: int = 20):
        import cognee

        results = await cognee.recall(query, top_k=top_k)
        return results


async def initialize_cognee_graph(df: pd.DataFrame) -> CogneeGraph:
    cg = CogneeGraph()
    await cg.ingest(df)
    return cg
