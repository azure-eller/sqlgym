"""Every bundled problem has a working solution, and "next" picks the right problem."""

import pytest

from sqlgym import db, problems

ALL = problems.all_problems()


def test_problem_numbers_are_unique():
    numbers = [p.number for p in ALL]
    assert len(numbers) == len(set(numbers))


@pytest.mark.parametrize("problem", ALL, ids=[p.slug for p in ALL])
def test_solution_runs_and_returns_rows(problem):
    query = db.last_statement(problem.solution_sql)
    assert db.run(db.fresh_db(problem.setup_sql), query).rows


def test_next_problem_prefers_untouched_then_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(problems, "PROGRESS_FILE", tmp_path / "progress.json")
    monkeypatch.setattr(problems, "DATA_DIR", tmp_path)
    first, second, third = ALL[:3]

    assert problems.next_problem() == first
    problems.mark(first, "skipped")
    assert problems.next_problem() == second
    problems.mark(second, "solved")
    assert problems.next_problem(after=first) == third
    problems.mark(second, "skipped")  # a skip never un-solves
    assert problems.load_progress()[second.slug] == "solved"

    for p in ALL[2:]:
        problems.mark(p, "solved")
    assert problems.next_problem(after=first) == first  # only the skipped one is left
    problems.mark(first, "solved")
    assert problems.next_problem() is None
