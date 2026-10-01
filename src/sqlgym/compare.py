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


def matches(yours, expected, ordered: bool = False) -> bool:
    """Compare two lists of rows by position, ignoring column names.

    Floats are rounded to 4 places, NULL equals NULL, and row order only
    matters when `ordered` is true.
    """
    yours = [tuple(_norm(v) for v in row) for row in yours]
    expected = [tuple(_norm(v) for v in row) for row in expected]
    return yours == expected if ordered else Counter(yours) == Counter(expected)
