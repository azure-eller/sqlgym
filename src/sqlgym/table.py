"""Plain-text tables in psql's style, for the problem pane and query results."""

import unicodedata
from decimal import Decimal

NUMBER = (int, float, Decimal)


def render(columns: list[str], rows: list[tuple], limit: int | None = None) -> list[str]:
    """Header centred, numbers right-aligned, everything else left-aligned.

    `limit` truncates long cells (used for the sample rows in the problem pane).
    """
    cells = [[_cell(v, limit) for v in row] for row in rows]
    widths = [max([_width(c)] + [_width(r[i]) for r in cells]) for i, c in enumerate(columns)]
    numeric = [any(isinstance(row[i], NUMBER) for row in rows) for i in range(len(columns))]

    def line(parts):
        return " " + " | ".join(parts).rstrip()

    def pad(s, w, align):
        gap = w - _width(s)
        left = {"left": 0, "right": gap, "center": gap // 2}[align]
        return " " * left + s + " " * (gap - left)

    out = [line(pad(c, w, "center") for c, w in zip(columns, widths))]
    out.append("+".join("-" * (w + 2) for w in widths))
    for row in cells:
        out.append(line(pad(c, w, "right" if num else "left") for c, w, num in zip(row, widths, numeric)))
    return out


def _width(s: str) -> int:
    """Columns `s` takes in a terminal: wide (CJK, emoji) characters take two, combining marks none."""
    return sum(
        0 if unicodedata.combining(ch) else 2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s
    )


def _cell(value, limit: int | None) -> str:
    s = "NULL" if value is None else str(value)
    return s if limit is None or len(s) <= limit else s[: limit - 1] + "…"
