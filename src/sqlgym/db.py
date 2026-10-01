"""Thin DuckDB helpers: fresh databases, last-statement extraction, introspection."""

from dataclasses import dataclass

import duckdb

Error = duckdb.Error


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]


def fresh_db(setup_sql: str) -> duckdb.DuckDBPyConnection:
    """A new in-memory database with setup.sql applied."""
    con = duckdb.connect(":memory:")
    con.execute(setup_sql)
    return con


def last_statement(sql: str) -> str | None:
    """The last SQL statement in `sql`, or None if it has none (only comments).

    Uses DuckDB's own parser, so semicolons inside strings or comments are
    handled correctly. Raises duckdb.Error if the text doesn't parse.
    """
    statements = duckdb.extract_statements(sql)
    return statements[-1].query.strip() if statements else None


def run(con: duckdb.DuckDBPyConnection, query: str) -> QueryResult:
    cursor = con.execute(query)
    if cursor.description is None:
        raise duckdb.InvalidInputException("The last statement didn't return any rows. End the file with a SELECT.")
    return QueryResult([d[0] for d in cursor.description], cursor.fetchall())


def describe_tables(con: duckdb.DuckDBPyConnection, sample_rows: int = 3):
    """Yield (qualified name, [(column, type)], QueryResult of first rows) per table."""
    tables = con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_type = 'BASE TABLE' ORDER BY table_schema <> 'main', table_schema, table_name"
    ).fetchall()
    for schema, table in tables:
        ref = f'"{schema}"."{table}"'
        name = table if schema == "main" else f"{schema}.{table}"
        columns = [(r[0], r[1]) for r in con.execute(f"DESCRIBE {ref}").fetchall()]
        yield name, columns, run(con, f"SELECT * FROM {ref} LIMIT {sample_rows}")
