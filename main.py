import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from src.config import DATA_PATH, OUTPUT_DIR
from src.filter_pipeline import load_and_filter_data
from src.graph_builder import (
    build_ac_to_ac_graph,
    build_full_graph,
    find_connected_components,
    find_loops,
    compute_total_exposure,
    initialize_cognee_graph,
)
from src.behavioral_analyzer import analyze_all
from src.adjudicator import adjudicate


async def main():
    print("Step 1: Loading and filtering data...")
    filtered_df, metadata = load_and_filter_data(str(DATA_PATH))
    print(f"  Total transactions: {metadata['total_transactions']}")
    print(f"  Total accounts: {metadata['total_accounts']}")
    print(f"  Heuristic filtered: {metadata['heuristic_filtered']}")
    print(f"  AC-to-AC transactions: {metadata['ac_to_ac_count']}")

    full_df = pd.read_csv(str(DATA_PATH), parse_dates=['timestamp', 'account_open_date'])

    metadata['heuristic_accounts'] = list(
        filtered_df[filtered_df['in_heuristic']]['account_id'].unique()
    )
    metadata['ac_to_ac_accounts'] = list(
        filtered_df[filtered_df['in_ac_to_ac']]['account_id'].unique()
    )

    print("\nStep 2: Building AC-to-AC graph and finding loops...")
    ac_df = full_df[full_df['counterparty_id'].str.startswith('AC-')]
    G_ac = build_ac_to_ac_graph(ac_df)
    print(f"  AC-to-AC graph: {G_ac.number_of_nodes()} nodes, {G_ac.number_of_edges()} edges")

    components = find_connected_components(G_ac)
    print(f"  Connected components: {len(components)}")
    for i, comp in enumerate(components):
        print(f"    Component {i}: {len(comp)} accounts: {sorted(comp)}")

    loops = find_loops(ac_df)
    print(f"  Circular loops found: {len(loops)}")
    for l in loops:
        print(f"    {l['sender']} -> {l['receiver']}: "
              f"{l['txn_count']} txns, ${l['total_amount']:,.2f}")

    total_exposure = compute_total_exposure(loops)
    print(f"  Total exposure: ${total_exposure:,.2f}")

    scc_accounts = set()
    for comp in components:
        scc_accounts.update(comp)

    print("\nStep 2b: Building full transaction graph...")
    G_full = build_full_graph(full_df)
    print(f"  Full graph: {G_full.number_of_nodes()} nodes, {G_full.number_of_edges()} edges")

    print("\nStep 2c: Ingesting into Cognee knowledge graph...")
    try:
        cognee_graph = await initialize_cognee_graph(full_df)
        print("  Cognee ingestion complete.")
    except Exception as e:
        print(f"  Cognee ingestion skipped: {e}")

    print("\nStep 3: Analyzing behavioral signals...")
    behavioral_signals = analyze_all(full_df)
    drift_count = sum(
        1 for v in behavioral_signals['drift_candidates'].values() if v.get('drift')
    )
    regular_count = sum(
        1 for v in behavioral_signals['timing_regularity'].values() if v.get('within_cluster_regular')
    )
    shared_count = behavioral_signals['shared_devices']['count']
    print(f"  Behavioral drift accounts: {drift_count}")
    print(f"  Regular timing accounts: {regular_count}")
    print(f"  Shared device fingerprints: {shared_count}")

    print("\nStep 4: Adjudicating...")
    result = adjudicate(
        loops=loops,
        total_exposure=total_exposure,
        scc_accounts=scc_accounts,
        metadata=metadata,
        behavioral_signals=behavioral_signals,
        G=G_full,
    )
    print(f"  Ring members identified: {len(result['ring_members'])}")
    print(f"  Exonerated accounts: {len(result['exonerated_accounts'])}")
    print(f"  Total exposure: ${result['total_exposure']:,.2f}")
    print(f"  Loops found: {len(result['loops'])}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / 'detection_result.json'
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")

    print("\n--- Final Output ---")
    print(json.dumps({
        'ring_members': result['ring_members'],
        'exonerated_accounts': result['exonerated_accounts'],
        'total_exposure': result['total_exposure'],
        'loops': [{'loop_id': l['loop_id'], 'path': l['path']} for l in result['loops']],
        'narrative': result['narrative'],
    }, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
