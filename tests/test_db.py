"""Only the last statement in the SQL pane is checked."""

import pytest

from sqlgym import db


def test_last_statement_is_the_one_checked():
    assert db.last_statement("select 1;\nselect 2 as x;").rstrip(";").endswith("select 2 as x")
    assert db.last_statement("select 1; select 2").endswith("select 2")
    # Semicolons inside strings and comments don't split statements.
    assert db.last_statement("select 1;\nselect 'a;b' as s -- trailing; comment\n").startswith("select 'a;b'")


def test_comments_only_is_no_query():
    assert db.last_statement("-- thinking...\n\n") is None


def test_parse_errors_raise():
    with pytest.raises(db.Error):
        db.last_statement("selec 1")


def test_tables_line_up_with_wide_characters():
    from sqlgym import table

    lines = table.render(["name", "n"], [("日本語", 1), ("abc", 22)])
    assert lines == ["  name  | n", "--------+----", " 日本語 |  1", " abc    | 22"]
