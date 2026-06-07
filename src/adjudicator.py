import json
from collections import defaultdict
from src.config import (
    USE_LLM, LLM_MODEL, LLM_API_KEY, LLM_API_BASE,
    SHARED_DEVICE_WEIGHT, DRIFT_WEIGHT, OPEN_DATE_WEIGHT,
    TIMING_REGULARITY_WEIGHT, SCC_WEIGHT, DISTRACTOR_PENALTY, RING_THRESHOLD,
)


def adjudicate(
    loops: list,
    total_exposure: float,
    scc_accounts: set,
    metadata: dict,
    behavioral_signals: dict,
    G,
) -> dict:
    open_date_cluster = set(metadata.get('open_date_cluster_accounts', []))
    heuristic_accounts = set(metadata.get('heuristic_accounts', []))
    ac_to_ac_accounts = set(metadata.get('ac_to_ac_accounts', []))

    all_loop_accounts = set()
    for loop in loops:
        all_loop_accounts.add(loop['sender'])
        all_loop_accounts.add(loop['receiver'])

    all_candidate_accounts = set()
    all_candidate_accounts.update(all_loop_accounts)
    all_candidate_accounts.update(open_date_cluster)
    all_candidate_accounts.update(ac_to_ac_accounts)

    drift_data = behavioral_signals.get('drift_candidates', {})
    timing_data = behavioral_signals.get('timing_regularity', {})
    shared_devices_data = behavioral_signals.get('shared_devices', {})
    account_summary = behavioral_signals.get('account_summary', {})

    account_devices = defaultdict(set)
    for device, accounts in shared_devices_data.get('shared_devices', {}).items():
        for acc in accounts:
            account_devices[acc].add(device)

    scores = {}
    signal_details = {}

    for acc in all_candidate_accounts:
        score = 0.0
        signals = []

        if acc in scc_accounts:
            score += SCC_WEIGHT
            signals.append('in_scc')

        if acc in all_loop_accounts:
            score += 3.0
            signals.append('in_circular_loop')

        if acc in ac_to_ac_accounts:
            score += 1.0
            signals.append('ac_to_ac_sender')

        if acc in open_date_cluster:
            score += OPEN_DATE_WEIGHT
            signals.append('open_date_cluster')
        elif any(
            loop['sender'] == acc or loop['receiver'] == acc
            for loop in loops
        ):
            score += OPEN_DATE_WEIGHT * 0.5
            signals.append('ring_member')

        if acc in heuristic_accounts:
            score += 1.0
            signals.append('heuristic_match')

        drift_info = drift_data.get(acc, {})
        if drift_info.get('drift'):
            score += DRIFT_WEIGHT
            signals.append('behavioral_drift')

        timing_info = timing_data.get(acc, {})
        if timing_info.get('within_cluster_regular'):
            score += TIMING_REGULARITY_WEIGHT
            signals.append('regular_timing')

        if acc in account_devices:
            score += SHARED_DEVICE_WEIGHT
            signals.append('shared_device')

        if _is_likely_distractor(acc, all_loop_accounts, account_summary, behavioral_signals):
            score -= DISTRACTOR_PENALTY
            signals.append('distractor_penalty')

        scores[acc] = round(score, 2)
        signal_details[acc] = signals

    sorted_accounts = sorted(scores.items(), key=lambda x: -x[1])

    ring_members = [acc for acc, s in sorted_accounts if s >= RING_THRESHOLD]
    candidates = [acc for acc, s in sorted_accounts if RING_THRESHOLD > s >= 2.0]
    exonerated = _find_exonerated(ring_members, candidates, all_loop_accounts,
                                   account_summary, behavioral_signals)

    cycle_paths = []
    for i, loop in enumerate(loops):
        cycle_paths.append({
            'loop_id': f'LOOP-{i + 1:02d}',
            'path': [loop['sender'], loop['receiver']],
            'exposure': loop['total_amount'],
            'txn_count': loop['txn_count'],
        })

    result = {
        'ring_members': sorted(set(ring_members) - set(exonerated)),
        'exonerated_accounts': sorted(exonerated),
        'total_exposure': round(total_exposure, 2),
        'loops': cycle_paths,
        'candidate_accounts': sorted(candidates),
        'account_scores': {acc: {'score': scores[acc], 'signals': signal_details[acc]}
                           for acc in sorted(scores.keys())},
    }

    if USE_LLM:
        try:
            narrative = _generate_llm_narrative(result, behavioral_signals, metadata)
            result['narrative'] = narrative
        except Exception as e:
            result['narrative'] = f'LLM narrative generation failed: {e}'
    else:
        result['narrative'] = _generate_fallback_narrative(result)

    return result


def _is_likely_distractor(acc: str, loop_accounts: set, account_summary: dict,
                          behavioral_signals: dict) -> bool:
    summary = account_summary.get(acc, {})
    if not summary:
        return False

    ip_anomalies = behavioral_signals.get('ip_anomalies', {})

    if acc in loop_accounts:
        return False

    has_ip_anomaly = acc in ip_anomalies
    large_txns = summary.get('avg_amount', 0) > 500

    return has_ip_anomaly or large_txns


def _find_exonerated(ring_members: list, candidates: list, loop_accounts: set,
                     account_summary: dict, behavioral_signals: dict) -> list:
    exonerated = []
    for acc in ring_members + candidates:
        if _is_likely_distractor(acc, loop_accounts, account_summary, behavioral_signals):
            exonerated.append(acc)
    return list(set(exonerated))[:20]


def _generate_fallback_narrative(result: dict) -> str:
    return (
        f"Detection pipeline identified {len(result['ring_members'])} ring members "
        f"across {len(result['loops'])} circular loops with total exposure "
        f"${result['total_exposure']:,.2f}. "
        f"{len(result['exonerated_accounts'])} accounts were exonerated as false positives. "
        f"Run with USE_LLM=true for an AI-generated narrative."
    )


def _generate_llm_narrative(result: dict, behavioral_signals: dict, metadata: dict) -> str:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    llm_kwargs = {'model': LLM_MODEL}
    if LLM_API_BASE:
        llm_kwargs['base_url'] = LLM_API_BASE
    if LLM_API_KEY:
        llm_kwargs['api_key'] = LLM_API_KEY

    llm = ChatOpenAI(**llm_kwargs)

    system_prompt = (
        "You are a fraud investigation lead. Summarize the findings concisely. "
        "Explain the ring structure, how it was detected, and the key evidence."
    )

    context = json.dumps({
        'ring_members': result['ring_members'],
        'total_exposure': result['total_exposure'],
        'loops': result['loops'],
        'exonerated': result['exonerated_accounts'],
        'total_transactions': metadata.get('total_transactions', 0),
        'total_accounts': metadata.get('total_accounts', 0),
    }, indent=2)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Analyze these fraud detection results:\n{context}"),
    ]

    response = llm.invoke(messages)
    return response.content
