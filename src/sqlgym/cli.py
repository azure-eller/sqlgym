"""sqlgym: practice SQL interview problems in Neovim.

    sqlgym              open the next unsolved problem
    sqlgym open NNN     open a specific problem
    sqlgym list         list problems and your progress
    sqlgym run FILE     run the last query in FILE and print its output
    sqlgym check FILE   run the last query in FILE and check it
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from sqlgym import db, problems, table
from sqlgym.compare import difference

console = Console(highlight=False)
MAX_ROWS = 50  # rows shown before truncating a result table

# `sqlgym check` exit codes; nvim.lua picks the key hints to show from these.
PASSED, FAILED, SQL_ERROR, NO_QUERY = 0, 1, 2, 3


def main() -> None:
    parser = argparse.ArgumentParser(prog="sqlgym", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="command", metavar="{open,list,run,check}")
    p_open = sub.add_parser("open", help="open a specific problem")
    p_open.add_argument("number")
    sub.add_parser("list", help="list problems and your progress")
    p_run = sub.add_parser("run", help="run the last query in FILE")
    p_run.add_argument("file", type=Path)
    p_check = sub.add_parser("check", help="run the last query in FILE and check it")
    p_check.add_argument("file", type=Path)
    # Used by the nvim UI.
    p_answer = sub.add_parser("answer")
    p_answer.add_argument("problem")
    p_load = sub.add_parser("_load")
    p_load.add_argument("--slug")
    p_load.add_argument("--after")
    p_load.add_argument("--width", type=int, default=80)
    args = parser.parse_args()

    try:
        if args.command == "list":
            cmd_list()
        elif args.command == "run":
            sys.exit(cmd_run(args.file))
        elif args.command == "check":
            sys.exit(cmd_check(args.file))
        elif args.command == "answer":
            print(require_problem(args.problem).solution_sql)
        elif args.command == "_load":
            print(json.dumps(load_for_nvim(args.slug, args.after, args.width)))
        elif args.command == "open":
            launch(require_problem(args.number))
        else:
            launch(problems.next_problem())
    except KeyboardInterrupt:
        pass


def require_problem(ref: str) -> problems.Problem:
    problem = problems.find_problem(ref)
    if problem is None:
        sys.exit(f"No problem {ref}. Try `sqlgym list`.")
    return problem


# --- commands ----------------------------------------------------------------


def cmd_list() -> None:
    progress = problems.load_progress()
    listing = Table(box=None, header_style="bold")
    for col in ("#", "title", "difficulty", "status"):
        listing.add_column(col)
    status_style = {"solved": "[green]✓ solved[/]", "skipped": "[yellow]skipped[/]"}
    for p in problems.all_problems():
        listing.add_row(f"{p.number:03d}", escape(p.title), p.difficulty, status_style.get(progress.get(p.slug), ""))
    console.print(listing)
    print_progress()


def print_progress() -> None:
    solved = sum(1 for s in problems.load_progress().values() if s == "solved")
    console.print(f"{solved} of {len(problems.all_problems())} solved")


def problem_for_file(file: Path) -> problems.Problem | None:
    if not file.is_file():
        console.print(f"No such file: {escape(str(file))}", style="red")
        return None
    problem = problems.find_problem(file.name)
    if problem is None:
        console.print(f"Can't tell which problem {escape(file.name)} belongs to. Name it <NNN_slug>.sql.", style="red")
    return problem


def cmd_run(file: Path) -> int:
    problem = problem_for_file(file)
    if problem is None:
        return 1
    try:
        query = db.last_statement(file.read_text())
        if query is None:
            console.print("No query yet.", style="yellow")
            return 0
        result = db.run(db.fresh_db(problem.setup_sql), query)
    except db.Error as e:
        console.print(escape(str(e)), style="red")
        return 1
    print_result(result.columns, result.rows)
    return 0


def cmd_check(file: Path) -> int:
    """Run the file's last query, print whether it's right, then its result."""
    problem = problem_for_file(file)
    if problem is None:
        return SQL_ERROR
    try:
        query = db.last_statement(file.read_text())
        if query is None:
            print("No query yet. Write one in the SQL pane.")
            return NO_QUERY
        yours = db.run(db.fresh_db(problem.setup_sql), query)
    except db.Error as e:
        print("✗ Your query failed:")
        print(e)
        return SQL_ERROR

    expected = db.run(db.fresh_db(problem.setup_sql), problem.solution_sql)
    wrong = difference(yours, expected, problem.ordered)
    if not wrong:
        problems.mark(problem, "solved")
    print(f"✗ {wrong}\n" if wrong else "✓ Correct.\n")
    print_result(yours.columns, yours.rows)
    return FAILED if wrong else PASSED


def print_result(columns: list[str], rows: list[tuple]) -> None:
    """Print rows as a psql-style table (wide tables scroll sideways in the pane)."""
    for line in table.render(columns, rows[:MAX_ROWS]):
        print(line)
    if len(rows) > MAX_ROWS:
        print(f"… {len(rows) - MAX_ROWS} more rows")
    print(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")


# --- nvim -----------------------------------------------------------------------


def load_for_nvim(slug: str | None, after: str | None, width: int = 80) -> dict:
    """The problem nvim should show: `slug`, else the next one after `after`.

    Moving on from an unsolved problem marks it skipped.
    """
    if slug:
        problem = problems.find_problem(slug)
    else:
        current = problems.find_problem(after) if after else None
        if current and problems.load_progress().get(current.slug) != "solved":
            problems.mark(current, "skipped")
        problem = problems.next_problem(after=current)
    if problem is None:
        return {"done": True}
    lines, marks = problems.problem_text(problem, width)
    return {
        "slug": problem.slug,
        "header": " · ".join([f"Problem {problem.number}", problem.difficulty] + (["ordered"] if problem.ordered else [])),
        "work_file": str(problems.ensure_work_file(problem)),
        "lines": lines,
        "marks": marks,
    }


def launch(problem: problems.Problem | None) -> None:
    """Open the three-pane practice session in nvim (see nvim.lua)."""
    if problem is None:
        console.print("Nothing left to solve. Nice work!", style="green")
        return
    nvim = shutil.which("nvim")
    if nvim is None:
        sys.exit("sqlgym needs Neovim 0.10 or newer: https://neovim.io")
    opts = {
        # Run through this interpreter so it works even when `sqlgym` isn't on PATH.
        "cmd": [sys.executable, "-m", "sqlgym"],
        "slug": problem.slug,
        "work_dir": str(problems.WORK_DIR),
    }
    lua_file = Path(__file__).with_name("nvim.lua")
    setup = f"lua dofile({json.dumps(str(lua_file))}).start(vim.json.decode({json.dumps(json.dumps(opts))}))"
    # Open nvim on the work file (so no start screen takes over); nvim.lua
    # builds the problem and results panes around it.
    subprocess.run([nvim, str(problems.ensure_work_file(problem)), "-c", setup])
    print_progress()
