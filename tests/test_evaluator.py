import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluator import score, _precision, _recall, _f1


def test_perfect_score():
    result = {
        'ring_members': ['AC-0001', 'AC-0005'],
        'exonerated_accounts': ['AC-0100'],
        'total_exposure': 50000.0,
        'loops': [
            {'path': ['AC-0001', 'AC-0002'], 'exposure': 25000.0},
        ]
    }
    answer_key = {
        'ring_members': ['AC-0001', 'AC-0005'],
        'exonerated_accounts': ['AC-0100'],
        'total_exposure': 50000.0,
        'loops': [
            {'path': ['AC-0001', 'AC-0002'], 'exposure': 25000.0},
        ]
    }
    report = score(result, answer_key)
    assert report.ring_precision == 1.0
    assert report.ring_recall == 1.0
    assert report.ring_f1 == 1.0
    assert report.exposure_accuracy == 1.0


def test_partial_score():
    result = {
        'ring_members': ['AC-0001', 'AC-0009'],
        'exonerated_accounts': [],
        'total_exposure': 40000.0,
        'loops': [],
    }
    answer_key = {
        'ring_members': ['AC-0001', 'AC-0005'],
        'exonerated_accounts': ['AC-0100'],
        'total_exposure': 50000.0,
        'loops': [
            {'path': ['AC-0001', 'AC-0002'], 'exposure': 25000.0},
        ]
    }
    report = score(result, answer_key)
    assert report.ring_precision == 0.5
    assert report.ring_recall == 0.5
    assert report.ring_f1 == 0.5


def test_precision():
    assert _precision({'a', 'b'}, {'a', 'c'}) == 0.5
    assert _precision(set(), {'a'}) == 0.0
    assert _precision({'a'}, {'a'}) == 1.0


def test_recall():
    assert _recall({'a', 'b'}, {'a', 'c'}) == 0.5
    assert _recall(set(), {'a'}) == 0.0
    assert _recall({'a'}, {'a'}) == 1.0
    assert _recall(set(), set()) == 1.0


def test_f1():
    assert _f1(1.0, 1.0) == 1.0
    assert _f1(0.5, 0.5) == 0.5
    assert _f1(0.0, 0.5) == 0.0
    assert _f1(0.0, 0.0) == 0.0
