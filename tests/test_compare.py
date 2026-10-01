"""The rules for when your result counts as matching the expected one."""

from datetime import date
from decimal import Decimal

from sqlgym.compare import matches


def test_rows_must_match_exactly_ignoring_order():
    assert matches([(2, "b"), (1, "a")], [(1, "a"), (2, "b")])
    assert matches([], [])
    assert not matches([(1, "a"), (3, "c")], [(1, "a"), (2, "b")])  # wrong row
    assert not matches([(1,)], [(1,), (1,)])  # duplicates count
    assert not matches([(1, "a", None)], [(1, "a")])  # extra column


def test_order_matters_only_when_ordered():
    assert not matches([(2,), (1,)], [(1,), (2,)], ordered=True)
    assert matches([(1,), (2,)], [(1,), (2,)], ordered=True)


def test_values_compare_loosely_where_sql_would():
    assert matches([(0.333333333,)], [(1 / 3,)])  # floats rounded to 4 places
    assert not matches([(1.0002,)], [(1.0,)])
    assert matches([(Decimal("2.50"), 5)], [(2.5, 5.0)])  # decimal, float and int
    assert matches([(None, float("nan"))], [(None, float("nan"))])  # NULL = NULL, NaN = NaN
    assert not matches([(None,)], [(0,)])
    assert matches([([1, 2], {"a": 1.00001})], [([1, 2], {"a": 1.0})])  # lists and structs
    assert not matches([("2024-01-01",)], [(date(2024, 1, 1),)])  # no type coercion
