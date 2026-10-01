"""Import the exercises from https://github.com/AlisdairO/pgexercises into problems/.

    uv run scripts/import_pgexercises.py [--repo PATH]

Clones the repo (or uses --repo), converts the Postgres dump to DuckDB, turns
each SELECT exercise into a problem folder numbered 001-099, runs every
solution against DuckDB, and writes scripts/import_report.md listing anything
that was fixed up or skipped. Problems 001-099 are owned by this script and
are replaced on every run.
"""

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
PROBLEMS = ROOT / "problems"
REPORT = ROOT / "scripts" / "import_report.md"
REPO_URL = "https://github.com/AlisdairO/pgexercises"

# Category directories in the order the site presents them.
CATEGORIES = {
    "basic": "easy",
    "joins": "easy",
    "aggregates": "medium",
    "date": "medium",
    "string": "easy",
    "recursive": "hard",
}
SKIPPED_CATEGORIES = {"updates": "modifies data (INSERT/UPDATE/DELETE); sqlgym only checks SELECT results"}

# Postgres -> DuckDB rewrites for solutions that don't run (or mean something
# different) in DuckDB, keyed by "<category>/<name>". Each is (old, new).
FIXES: dict[str, list[tuple[str, str]]] = {
    # Postgres lets you select columns functionally dependent on a grouped
    # primary key; DuckDB needs them in the GROUP BY. `/` on integers is
    # integer division in Postgres but not in DuckDB, which spells it `//`.
    "aggregates/rankmembers": [
        ("((sum(bks.slots)+10)/20)*10 as", "((sum(bks.slots)+10)//20)*10 as"),
        ("((sum(bks.slots)+10)/20)*10 desc", "((sum(bks.slots)+10)//20)*10 desc"),
        ("group by mems.memid", "group by mems.memid, firstname, surname"),
    ],
    "aggregates/payback": [
        ("group by facs.facid", "group by facs.facid, facs.name, facs.initialoutlay, facs.monthlymaintenance"),
    ],
    "date/utilisationpermonth": [("group by facs.facid, month", "group by facs.facid, facs.name, month")],
    # No to_char in DuckDB.
    "aggregates/fachours3": [
        ("trim(to_char(sum(bks.slots)/2.0, '9999999999999999D99'))", "printf('%.2f', sum(bks.slots)/2.0)"),
    ],
    # generate_series() in DuckDB returns a list rather than a set of rows.
    "aggregates/rollingavg": [
        (
            "cast(generate_series(timestamp '2012-08-01',\n\t\t\t'2012-08-31','1 day') as date)",
            "cast(unnest(generate_series(timestamp '2012-08-01',\n\t\t\ttimestamp '2012-08-31', interval '1 day')) as date)",
        ),
    ],
    "date/series": [("select generate_series(", "select unnest(generate_series("), (") as ts", ")) as ts")],
    "date/daysinmonth": [
        ("select generate_series(", "select unnest(generate_series("),
        ("interval '1 month') as month", "interval '1 month')) as month"),
    ],
    # DuckDB can't infer the type of the untyped literal here.
    "date/interval2": [("- '2012-08-31 01:00:00'", "- timestamp '2012-08-31 01:00:00'")],
    # DuckDB's ~ must match the whole string; Postgres's matches anywhere.
    "string/reg": [("telephone ~ '[()]'", "regexp_matches(telephone, '[()]')")],
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, help="use an existing pgexercises checkout instead of cloning")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        repo = args.repo
        if repo is None:
            repo = Path(tmp) / "pgexercises"
            subprocess.run(["git", "clone", "--quiet", "--depth", "1", REPO_URL, str(repo)], check=True)
        import_repo(repo)


def import_repo(repo: Path) -> None:
    setup_sql = convert_dump((repo / "database" / "clubdata.sql").read_text())
    duckdb.connect().execute(setup_sql)  # fail fast if the conversion is broken

    for old in PROBLEMS.glob("0[0-9][0-9]_*"):
        shutil.rmtree(old)

    imported, fixed, skipped, unordered = [], [], [], []
    number = 0
    for category, difficulty in CATEGORIES.items():
        for ex_file in sorted((repo / "questions" / category).glob("*.ex")):
            ex = parse_ex(ex_file.read_text())
            name = ex_file.stem.split("-", 1)[1]
            key = f"{category}/{name}"
            if ex.get("WRITEABLE", "0").strip() == "1":
                skipped.append((key, ex["QUESTIONNAME"], "modifies data"))
                continue

            solution = ex["QUERY"].strip()
            for old, new in FIXES.get(key, []):
                if old not in solution:
                    sys.exit(f"{key}: fix no longer applies: {old!r}")
                solution = solution.replace(old, new)
            if key in FIXES:
                fixed.append((key, ex["QUESTIONNAME"], FIXES[key]))

            try:
                con = duckdb.connect()
                con.execute(setup_sql)
                rows = con.execute(solution).fetchall()
                ordered = has_top_level_order_by(con, solution)
                if ordered and order_has_ties(setup_sql, solution, rows):
                    ordered = False
                    unordered.append((key, ex["QUESTIONNAME"]))
            except duckdb.Error as e:
                skipped.append((key, ex["QUESTIONNAME"], f"fails in DuckDB: {str(e).splitlines()[0]}"))
                continue
            if not rows:
                skipped.append((key, ex["QUESTIONNAME"], "solution returns no rows"))
                continue

            number += 1
            write_problem(
                PROBLEMS / f"{number:03d}_{category}_{name.replace('-', '_')}",
                title=ex["QUESTIONNAME"].strip(),
                difficulty=difficulty,
                ordered=ordered,
                hint=html_to_text(ex.get("HINT", "")),
                prompt=html_to_text(ex["QUESTION"]),
                setup_sql=setup_sql,
                solution=solution,
            )
            imported.append(key)

    for category, reason in SKIPPED_CATEGORIES.items():
        for ex_file in sorted((repo / "questions" / category).glob("*.ex")):
            title = parse_ex(ex_file.read_text())["QUESTIONNAME"]
            skipped.append((f"{category}/{ex_file.stem.split('-', 1)[1]}", title, reason))
    write_report(imported, fixed, skipped, unordered)
    print(f"imported {len(imported)} problems, fixed {len(fixed)}, skipped {len(skipped)}; see {REPORT.relative_to(ROOT)}")


# --- converting the Postgres dump ------------------------------------------------

TYPES = [
    (r"character varying\(\d+\)", "VARCHAR"),
    (r"timestamp without time zone", "TIMESTAMP"),
    (r"\binteger\b", "INTEGER"),
    (r"\bnumeric\b", "DECIMAL(10, 2)"),
]


def convert_dump(dump: str) -> str:
    """Turn the pg_dump output into DuckDB CREATE TABLE + INSERT statements.

    DuckDB supports schemas, so tables keep living in `cd`.
    """
    out = ["CREATE SCHEMA cd;", ""]
    column_types: dict[str, list[str]] = {}

    for table, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", dump, re.S):
        columns = []
        for line in body.strip().splitlines():
            col, pg_type = line.strip().rstrip(",").split(" ", 1)
            pg_type = pg_type.replace(" NOT NULL", "")
            for pattern, duck_type in TYPES:
                pg_type = re.sub(pattern, duck_type, pg_type)
            columns.append((col, pg_type))
        column_types[table] = [t for _, t in columns]
        cols = ",\n".join(f"    {c} {t}" for c, t in columns)
        out += [f"CREATE TABLE cd.{table} (\n{cols}\n);", ""]

    for table, cols, data in re.findall(r"COPY (\w+) \((.*?)\) FROM stdin;\n(.*?)\n\\\.", dump, re.S):
        types = column_types[table]
        values = [
            "(" + ", ".join(sql_literal(v, t) for v, t in zip(line.split("\t"), types)) + ")"
            for line in data.splitlines()
        ]
        out.append(f"INSERT INTO cd.{table} ({cols}) VALUES\n" + ",\n".join(values) + ";\n")
    return "\n".join(out)


def sql_literal(value: str, sql_type: str) -> str:
    if value == r"\N":
        return "NULL"
    if sql_type in ("INTEGER",) or sql_type.startswith("DECIMAL"):
        return value
    return "'" + value.replace("'", "''") + "'"


# --- reading exercises -------------------------------------------------------------


def parse_ex(text: str) -> dict[str, str]:
    """Split a .ex file into its |SECTION| blocks."""
    parts = re.split(r"^\|([A-Z]+)\|$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip("\n") for i in range(1, len(parts), 2)}


def html_to_text(fragment: str) -> str:
    """The little HTML the exercises use, as plain text with `code` spans."""
    s = re.sub(r"\s+", " ", fragment)
    s = re.sub(r"<c>(.*?)</c>", r"`\1`", s)
    s = re.sub(r"<sql>(.*?)</sql>", r"`\1`", s)
    s = re.sub(r"<li>", "\n\n- ", s)
    s = re.sub(r"</?(p|div|ul)[^>]*>", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    paragraphs = [" ".join(p.split()) for p in s.split("\n\n")]
    return "\n\n".join(p for p in paragraphs if p)


def has_top_level_order_by(con: duckdb.DuckDBPyConnection, sql: str) -> bool:
    """True if the outermost query has an ORDER BY (not one inside a subquery)."""
    tree = json.loads(con.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()[0])
    node = tree["statements"][-1]["node"]
    return any(m["type"] == "ORDER_MODIFIER" for m in node.get("modifiers", []))


def order_has_ties(setup_sql: str, sql: str, rows: list) -> bool:
    """True if the solution's row order changes when the tables' rows are reversed.

    That means its ORDER BY doesn't fully determine the order, so a correct
    answer could legitimately come back in a different order.
    """
    con = duckdb.connect()
    con.execute("SET threads = 1")
    con.execute(setup_sql)
    for schema, table in con.execute("SELECT schema_name, table_name FROM duckdb_tables()").fetchall():
        con.execute(f"CREATE OR REPLACE TABLE {schema}.{table} AS SELECT * FROM {schema}.{table} ORDER BY rowid DESC")
    return con.execute(sql).fetchall() != rows


# --- writing -------------------------------------------------------------------------


def write_problem(path: Path, *, title, difficulty, ordered, hint, prompt, setup_sql, solution) -> None:
    path.mkdir(parents=True)
    toml = [f"title = {json.dumps(title)}", f'difficulty = "{difficulty}"', f"ordered = {str(ordered).lower()}"]
    if hint:
        toml.append(f"hint = {json.dumps(hint)}")
    (path / "problem.toml").write_text("\n".join(toml) + "\n")
    (path / "prompt.md").write_text(prompt + "\n")
    (path / "setup.sql").write_text(setup_sql)
    (path / "solution.sql").write_text(solution + "\n")


def write_report(imported, fixed, skipped, unordered) -> None:
    lines = ["# pgexercises import report", "", f"Imported {len(imported)} problems.", ""]
    lines += ["## Solutions rewritten for DuckDB", ""]
    for key, title, fixes in fixed:
        lines.append(f"- `{key}` ({title})")
        lines += [f"  - `{' '.join(old.split())}` → `{' '.join(new.split())}`" for old, new in fixes]
    lines += ["", "## ORDER BY leaves ties, so row order is not checked", ""]
    lines += [f"- `{key}` ({title.strip()})" for key, title in unordered]
    lines += ["", "## Skipped", ""]
    lines += [f"- `{key}` ({title.strip()}): {reason}" for key, title, reason in skipped]
    REPORT.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
