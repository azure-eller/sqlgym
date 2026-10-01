"""End-to-end UI tests: real sqlgym in real Neovim, driven through tmux.

Each test runs `sqlgym` in a private tmux server at a fixed size, presses keys
like a user, and checks the screen after every step with `check()`. Progress
and answers go to a scratch directory, never your real ones.

Neovim runs with an empty config by default. SQLGYM_TEST_USER_CONFIG=1 also
runs every test against your own Neovim config.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time

import pytest

from sqlgym import problems

pytestmark = pytest.mark.skipif(not (shutil.which("tmux") and shutil.which("nvim")), reason="needs tmux and nvim")

CONFIGS = ["clean"] + (["user"] if os.environ.get("SQLGYM_TEST_USER_CONFIG") else [])
ERRORS = re.compile(r"\bE\d{2,4}:|stack traceback|Error executing|ATTENTION|Press ENTER")
MIN_RESULTS = 8  # rows the results pane always keeps


class Session:
    """sqlgym in a tmux window of `width` x `height`."""

    def __init__(self, tmp_path, config, problem, width=100, height=40):
        self.socket = f"sqlgym-test-{os.getpid()}-{id(self)}"
        self.width, self.height = width, height
        self.data = tmp_path / "data"
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.sql = [""]  # what the SQL pane should contain
        env = {"SQLGYM_DATA_DIR": str(self.data)}
        if config == "clean":
            for var in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
                env[var] = str(tmp_path / var.lower())
        self.leader = "\\" if config == "clean" else " "
        self.cmdheight = 1 if config == "clean" else 0  # the user's LazyVim config hides the command line
        cmd = ["env", *(f"{k}={v}" for k, v in env.items()), sys.executable, "-m", "sqlgym", "open", str(problem)]
        self.tmux("new-session", "-d", "-x", str(width), "-y", str(height), shlex.join(cmd))
        self.tmux("set", "-g", "escape-time", "0")
        self.wait(lambda s: "─ Results" in s, timeout=30)

    def tmux(self, *args):
        return subprocess.run(["tmux", "-L", self.socket, *args], check=True, capture_output=True, text=True).stdout

    def screen(self, colors=False):
        return self.tmux("capture-pane", "-p", *(["-e"] if colors else []))

    def wait(self, ready=lambda s: True, timeout=15):
        """Wait until `ready(screen)` holds and the screen has stopped changing."""
        deadline, last = time.monotonic() + timeout, None
        while time.monotonic() < deadline:
            screen = self.screen()
            if ready(screen) and screen == last:
                return screen
            last = screen
            time.sleep(0.15)
        raise AssertionError(f"timed out; screen:\n{self.screen()}")

    def keys(self, *keys):
        self.tmux("send-keys", *keys)

    def type(self, lines):
        """Replace the SQL with `lines`, pasted (so no config's auto-pairs or auto-indent interfere)."""
        self.keys("g", "g", "d", "G", "i")
        paste = self.data.parent / "paste.sql"  # via a file: tmux reads a trailing ";" in an argument as a separator
        paste.write_text("\n".join(lines))
        self.tmux("load-buffer", str(paste))
        self.tmux("paste-buffer", "-p")  # bracketed paste, as a terminal sends it
        self.keys("Escape")
        self.sql = list(lines)
        self.wait(lambda scr: lines[-1].strip() in scr)  # the cursor ends on the last line, so it's in view

    def action(self, key):
        self.keys("-l", self.leader + key)

    def resize(self, width, height):
        self.width, self.height = width, height
        self.tmux("resize-window", "-x", str(width), "-y", str(height))

    def close(self):
        subprocess.run(["tmux", "-L", self.socket, "kill-server"], capture_output=True)


@pytest.fixture(params=CONFIGS)
def start(request, tmp_path):
    sessions = []

    def start(problem, **size):
        sessions.append(Session(tmp_path / str(len(sessions)), request.param, problem, **size))
        return sessions[-1]

    yield start
    for s in sessions:
        s.close()


# --- what must always be true on screen ----------------------------------------


def check(s: Session, screen: str) -> list[str]:
    """The layout and look the UI must always have. Returns the screen's lines."""
    lines = screen.split("\n")[: s.height]
    assert not ERRORS.search(screen), f"error on screen:\n{screen}"

    def bar(label):
        rows = [i for i, line in enumerate(lines) if line.startswith(f"─ {label}")]
        assert len(rows) == 1, f"expected one {label} bar, found {len(rows)}:\n{screen}"
        assert len(lines[rows[0]].rstrip()) == s.width, f"{label} bar isn't full width:\n{screen}"
        return rows[0]

    problem, sql, results = bar("Problem"), bar("SQL"), bar("Results")
    assert problem == 0 < sql < results, f"panes out of order:\n{screen}"
    for row in (sql, results):  # panes are separated by a blank line, nothing else
        assert lines[row - 1].strip() == "", f"clutter above row {row}: {lines[row - 1]!r}\n{screen}"

    # The SQL pane fits your query exactly; if it can't grow enough, it's
    # full of query (no blank rows while lines are hidden).
    shown = [line.strip() for line in lines[sql + 1 : results - 1]]  # (auto-indent may differ by config)
    want = [line.strip() for line in s.sql]
    if len(want) <= len(shown):
        assert shown == want, f"SQL pane shows {shown}, expected {want}:\n{screen}"
    else:
        assert any(shown == want[i : i + len(shown)] for i in range(len(want))), f"SQL pane shows {shown}:\n{screen}"

    # Results keep their minimum, and only take more when the problem isn't cut short.
    results_rows = s.height - 1 - s.cmdheight - (results + 1)
    if s.height >= 24:
        assert results_rows >= MIN_RESULTS, f"results squeezed to {results_rows} rows:\n{screen}"
    check_plain(s, sql, results)
    return lines


def check_plain(s: Session, sql: int, results: int):
    """No colour or italics/underline outside the SQL pane (its syntax colours are the editor's)."""
    seen, style = set(), {}  # tmux carries styles over from one line to the next
    for row, line in enumerate(s.screen(colors=True).split("\n")[: s.height - 1 - s.cmdheight]):
        for part in re.split(r"(\x1b\[[0-9;]*m)", line):
            if part.startswith("\x1b["):
                codes, i = part[2:-1].split(";"), 0
                while i < len(codes):
                    code = codes[i]
                    if code in ("", "0"):
                        style.clear()
                    elif code == "39":
                        style.pop("fg", None)
                    elif code == "38":
                        n = 5 if codes[i + 1] == "2" else 3
                        style["fg"], i = ";".join(codes[i : i + n]), i + n - 1
                    elif code in ("3", "4", "7"):
                        style[code] = True
                    elif code in ("23", "24", "27"):
                        style.pop(code[1], None)
                    elif code.isdigit() and (30 <= int(code) <= 37 or 90 <= int(code) <= 97):
                        style["fg"] = code
                    i += 1
            elif part.strip() and not sql < row < results:
                seen.add(tuple(sorted(style.items())))
    assert len(seen) <= 1, f"text in more than one style outside the SQL pane: {seen}"


def results_text(lines):
    start = next(i for i, line in enumerate(lines) if line.startswith("─ Results"))
    return "\n".join(lines[start + 1 :])


# --- tests ------------------------------------------------------------------------


def test_every_problem_renders(start):
    """Open problem 1 and press next through all of them; each shows its question."""
    s = start(1)
    for n, problem in enumerate(problems.all_problems()):
        if n:
            s.action("n")
        lines = check(s, s.wait(lambda scr: f"─ Problem {problem.number} " in scr))
        assert lines[2] == "  " + problems.problem_text(problem, s.width - 2)[0][1], f"problem {problem.number}"


def test_solving_a_problem(start):
    s = start(106)
    check(s, s.wait())

    # Wrong: the verdict, then your output.
    s.type(["select user_id, email", "from users", "where user_id < 4"])
    s.action("r")
    lines = check(s, s.wait(lambda scr: "Not quite" in scr))
    assert results_text(lines).lstrip().startswith("✗ Not quite.\n\n   user_id |")

    # Clearing from another pane shrinks the SQL pane back.
    s.keys("C-w", "j")
    s.action("R")
    s.sql = [""]
    check(s, s.wait(lambda scr: "Cleared" in scr))
    s.keys("C-w", "k")

    # Right: the verdict, and the problem is saved as solved.
    problem = problems.find_problem("106")
    s.type([line.strip() for line in problem.solution_sql.splitlines() if line.strip()])
    s.action("r")
    check(s, s.wait(lambda scr: "✓ Correct." in scr))
    assert json.loads((s.data / "progress.json").read_text())[problem.slug] == "solved"


@pytest.mark.parametrize("size", [(80, 24), (220, 60)])
def test_long_problem_and_query_at_small_and_large_sizes(start, size):
    width, height = size
    s = start(110, width=width, height=height)
    check(s, s.wait())
    s.type([f"select {n} as n union all" for n in range(14)] + ["select 99 as n"])
    check(s, s.wait(lambda scr: "select 99" in scr))
    s.action("r")
    check(s, s.wait(lambda scr: "Not quite" in scr))


def test_resizing_away_and_back_restores_the_screen(start):
    s = start(4)
    s.type(["select facid, name", "from cd.facilities"])
    s.action("r")
    before = check(s, s.wait(lambda scr: "Not quite" in scr))
    for width, height in [(80, 24), (160, 50), (100, 40)]:
        s.resize(width, height)
        check(s, s.wait())
    assert check(s, s.wait()) == before


def test_quitting_saves_your_sql(start):
    s = start(3)
    s.type(["select 42"])
    s.keys(":q", "Enter")
    work = s.data / "work" / f"{problems.find_problem('3').slug}.sql"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and "42" not in (work.read_text() if work.exists() else ""):
        time.sleep(0.1)
    assert work.read_text().strip() == "select 42"
