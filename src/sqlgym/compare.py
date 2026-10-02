"""Decide whether a query result matches the expected one. Pure: no I/O, no DuckDB."""

import math
from collections import Counter
from decimal import Decimal


def _norm(value):
    """Make a value comparable and hashable: round floats, flatten containers."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (float, Decimal)):
        f = float(value)
        if math.isnan(f):
            return "NaN"
        r = round(f, 4)
        return 0.0 if r == 0 else r  # fold -0.0 into 0.0
    if isinstance(value, (list, tuple)):
        return tuple(_norm(v) for v in value)
    if isinstance(value, dict):
        return tuple((k, _norm(v)) for k, v in value.items())
    return value


def _count(n, noun):
    return f"{n} {noun}" + ("" if n == 1 else "s")


def difference(yours, expected, ordered: bool = False) -> str | None:
    """None if your result matches the expected one, else the first way it differs.

    Results have `.columns` and `.rows`. Columns are compared by position, not
    name. Floats are rounded to 4 places, NULL equals NULL, and row order only
    matters when `ordered` is true.
    """
    rows = [tuple(_norm(v) for v in row) for row in yours.rows]
    want = [tuple(_norm(v) for v in row) for row in expected.rows]
    if len(yours.columns) != len(expected.columns):
        return f"Expected {_count(len(expected.columns), 'column')}, got {len(yours.columns)}."
    if len(rows) != len(want):
        return f"Expected {_count(len(want), 'row')}, got {len(rows)}."
    for i, name in enumerate(yours.columns):
        if Counter(row[i] for row in rows) != Counter(row[i] for row in want):
            return f"Wrong values in column {name}."
    if Counter(rows) != Counter(want):
        return "Right values, but in the wrong rows."
    if ordered and rows != want:
        return "Right rows, wrong order."
    return None
