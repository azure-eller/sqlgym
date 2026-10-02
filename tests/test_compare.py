"""The rules for when your result counts as matching the expected one."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlgym.compare import difference


def diff(yours, expected, ordered=False):
    """`difference` for bare rows, with columns named a, b, c, …"""
    result = lambda rows: SimpleNamespace(columns=list("abcdef")[: len(rows[0]) if rows else 1], rows=rows)
    return difference(result(yours), result(expected), ordered)


def test_each_difference_is_named():
    assert diff([(1, "a"), (2, "b")], [(1, "a"), (2, "b")]) is None
    assert diff([(1, "a", None)], [(1, "a")]) == "Expected 2 columns, got 3."
    assert diff([(1,), (1,)], [(1,)]) == "Expected 1 row, got 2."
    assert diff([(1, "a"), (2, "x")], [(1, "a"), (2, "b")]) == "Wrong values in column b."
    assert diff([(1, "b"), (2, "a")], [(1, "a"), (2, "b")]) == "Right values, but in the wrong rows."
    assert diff([(2,), (1,)], [(1,), (2,)]) is None
    assert diff([(2,), (1,)], [(1,), (2,)], ordered=True) == "Right rows, wrong order."


def test_values_compare_loosely_where_sql_would():
    assert diff([(0.333333333,)], [(1 / 3,)]) is None  # floats rounded to 4 places
    assert diff([(1.0002,)], [(1.0,)])
    assert diff([(Decimal("2.50"), 5)], [(2.5, 5.0)]) is None  # decimal, float and int
    assert diff([(None, float("nan"))], [(None, float("nan"))]) is None  # NULL = NULL, NaN = NaN
    assert diff([(None,)], [(0,)])
    assert diff([([1, 2], {"a": 1.00001})], [([1, 2], {"a": 1.0})]) is None  # lists and structs
    assert diff([("2024-01-01",)], [(date(2024, 1, 1),)])  # no type coercion
