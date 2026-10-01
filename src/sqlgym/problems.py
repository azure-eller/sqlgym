"""Problem loading, the generated header, work files and progress (XDG storage)."""

import json
import os
import textwrap
import tomllib
from dataclasses import dataclass
from pathlib import Path

from sqlgym import db, table

HERE = Path(__file__).parent
# Installed: problems/ is bundled inside the package. Dev checkout: repo root.
PROBLEMS_DIR = next(
    (p for p in (HERE / "problems", HERE.parent.parent / "problems") if p.is_dir()),
    HERE / "problems",
)
# SQLGYM_DATA_DIR lets the UI tests use a scratch directory.
DATA_DIR = Path(
    os.environ.get("SQLGYM_DATA_DIR") or Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "sqlgym"
)
WORK_DIR = DATA_DIR / "work"
PROGRESS_FILE = DATA_DIR / "progress.json"


@dataclass
class Problem:
    number: int
    slug: str  # folder name, e.g. "007_basic_where"
    title: str
    difficulty: str
    ordered: bool
    path: Path

    @property
    def prompt(self) -> str:
        return (self.path / "prompt.md").read_text().strip()

    @property
    def setup_sql(self) -> str:
        return (self.path / "setup.sql").read_text()

    @property
    def solution_sql(self) -> str:
        return (self.path / "solution.sql").read_text().strip()

    @property
    def work_file(self) -> Path:
        return WORK_DIR / f"{self.slug}.sql"


def load_problem(path: Path) -> Problem:
    meta = tomllib.loads((path / "problem.toml").read_text())
    return Problem(
        number=int(path.name.split("_", 1)[0]),
        slug=path.name,
        title=meta["title"],
        difficulty=meta.get("difficulty", "medium"),
        ordered=meta.get("ordered", False),
        path=path,
    )


def all_problems() -> list[Problem]:
    dirs = [p for p in PROBLEMS_DIR.iterdir() if (p / "problem.toml").is_file()]
    return sorted((load_problem(p) for p in dirs), key=lambda p: p.number)


def find_problem(ref: str) -> Problem | None:
    """Look a problem up by number ("7", "007") or by work-file name/slug."""
    stem = Path(ref).stem
    for problem in all_problems():
        if stem == problem.slug or (stem.isdigit() and int(stem) == problem.number):
            return problem
    return None


# --- progress ----------------------------------------------------------------
# progress.json maps slug -> "solved" | "skipped". Absent means unsolved.


def load_progress() -> dict[str, str]:
    try:
        return json.loads(PROGRESS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def mark(problem: Problem, status: str) -> None:
    progress = load_progress()
    if progress.get(problem.slug) == "solved" and status != "solved":
        return  # a skip never un-solves a problem
    progress[problem.slug] = status
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2, sort_keys=True) + "\n")


def next_problem(after: Problem | None = None) -> Problem | None:
    """The next untouched problem after `after` (wrapping), else the next skipped one."""
    problems, progress = all_problems(), load_progress()
    start = next((i + 1 for i, p in enumerate(problems) if after and p.slug == after.slug), 0)
    rotated = problems[start:] + problems[:start]
    for wanted in (None, "skipped"):
        for p in rotated:
            if progress.get(p.slug) == wanted:
                return p
    return None


# --- work files ----------------------------------------------------------------

def ensure_work_file(problem: Problem) -> Path:
    """The user's .sql file for `problem`, created empty if needed."""
    path = problem.work_file
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    return path


def problem_text(problem: Problem, width: int = 80) -> tuple[list[str], list[tuple[int, str]]]:
    """The problem pane's lines (prompt, then each table), plus (line index, kind) highlights.

    The prompt is wrapped to `width`; tables are never wrapped (the pane
    scrolls sideways instead), so their columns always line up.
    """
    lines: list[str] = []
    marks: list[tuple[int, str]] = []

    def add(line: str = "", kind: str | None = None) -> None:
        if kind:
            marks.append((len(lines), kind))
        lines.append(line)

    add()  # breathing room under the pane's title bar
    for para in problem.prompt.split("\n\n"):
        # Prompts mark code with markdown backticks; the pane shows plain text.
        for line in textwrap.wrap(" ".join(para.replace("`", "").split()), max(width - 1, 20)):
            add(line, "question")
        add()

    con = db.fresh_db(problem.setup_sql)
    for name, columns, sample in db.describe_tables(con):
        add(name, "table")
        for line in table.render([c for c, _ in columns], sample.rows, limit=24):
            add(line)
        add()
    lines.pop()  # the gap below the pane is the space before the next one
    return lines, marks
