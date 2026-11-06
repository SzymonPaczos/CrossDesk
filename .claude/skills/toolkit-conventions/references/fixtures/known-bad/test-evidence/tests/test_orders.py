import sys

sys.modules.pop("src.orders", None)
sys.path.insert(0, "src")

from src.orders import total


def test_total_runs():
    total([1, 2])


def test_total_sums_items():
    assert total([1, 2]) == 3
