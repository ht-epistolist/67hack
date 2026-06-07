import json


class EvaluationReport:
    def __init__(self):
        self.ring_precision = 0.0
        self.ring_recall = 0.0
        self.ring_f1 = 0.0
        self.exonerated_precision = 0.0
        self.exonerated_recall = 0.0
        self.exonerated_f1 = 0.0
        self.exposure_accuracy = 0.0
        self.loop_overlap = 0.0
        self.composite_score = 0.0
        self.details = {}

    def to_dict(self) -> dict:
        return {
            'ring_member_metrics': {
                'precision': round(self.ring_precision, 4),
                'recall': round(self.ring_recall, 4),
                'f1': round(self.ring_f1, 4),
            },
            'exonerated_metrics': {
                'precision': round(self.exonerated_precision, 4),
                'recall': round(self.exonerated_recall, 4),
                'f1': round(self.exonerated_f1, 4),
            },
            'exposure_accuracy': round(self.exposure_accuracy, 4),
            'loop_overlap': round(self.loop_overlap, 4),
            'composite_score': round(self.composite_score, 4),
            'details': self.details,
        }


def score(result: dict, answer_key: dict) -> EvaluationReport:
    report = EvaluationReport()

    detected_ring = set(result.get('ring_members', []))
    true_ring = set(answer_key.get('ring_members', []))
    detected_exonerated = set(result.get('exonerated_accounts', []))
    true_exonerated = set(answer_key.get('exonerated_accounts', []))
    detected_exposure = result.get('total_exposure', 0.0)
    true_exposure = answer_key.get('total_exposure', 0.0)
    detected_loops = result.get('loops', [])
    true_loops = answer_key.get('loops', [])

    report.ring_precision = _precision(detected_ring, true_ring)
    report.ring_recall = _recall(detected_ring, true_ring)
    report.ring_f1 = _f1(report.ring_precision, report.ring_recall)

    report.exonerated_precision = _precision(detected_exonerated, true_exonerated)
    report.exonerated_recall = _recall(detected_exonerated, true_exonerated)
    report.exonerated_f1 = _f1(report.exonerated_precision, report.exonerated_recall)

    if true_exposure > 0:
        report.exposure_accuracy = 1.0 - min(
            abs(detected_exposure - true_exposure) / true_exposure, 1.0
        )

    report.loop_overlap = _loop_overlap(detected_loops, true_loops)

    report.composite_score = (
        report.ring_f1 * 0.4
        + report.exonerated_f1 * 0.2
        + report.exposure_accuracy * 0.2
        + report.loop_overlap * 0.2
    )

    report.details = {
        'true_ring_count': len(true_ring),
        'detected_ring_count': len(detected_ring),
        'true_exonerated_count': len(true_exonerated),
        'detected_exonerated_count': len(detected_exonerated),
        'true_exposure': true_exposure,
        'detected_exposure': detected_exposure,
        'true_loop_count': len(true_loops),
        'detected_loop_count': len(detected_loops),
    }

    return report


def _precision(detected: set, truth: set) -> float:
    if not detected:
        return 0.0
    return len(detected & truth) / len(detected)


def _recall(detected: set, truth: set) -> float:
    if not truth:
        return 0.0 if detected else 1.0
    return len(detected & truth) / len(truth)


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _loop_overlap(detected: list, truth: list) -> float:
    if not truth:
        return 1.0 if not detected else 0.0
    if not detected:
        return 0.0

    def path_to_set(loop):
        return set(loop.get('path', loop.get('path', [])))

    true_sets = [path_to_set(l) for l in truth]
    detected_sets = [path_to_set(l) for l in detected]

    scores = []
    for ds in detected_sets:
        best = max((len(ds & ts) / max(len(ds | ts), 1)) for ts in true_sets)
        scores.append(best)

    return sum(scores) / len(scores) if scores else 0.0
