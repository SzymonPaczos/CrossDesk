from src.orders import total


def test_total_sums_items():
    assert total([1, 2]) == 3


def test_total_of_empty_is_zero():
    assert total([]) == 0
