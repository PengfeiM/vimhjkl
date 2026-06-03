"""Headless verification of the grader across all 7 categories.

Uses `vim -s` keystroke playback (no manual editing) so the grading core —
buffer diff, cursor capture, keystroke counting, quit-stripping — is checked
end-to-end against real vim.  Run with:  python -m tests.test_grader
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vimhjkl.challenge import Challenge
from vimhjkl.grader import (
    run_attempt, find_editor, count_keystrokes, strip_quit, _last_command_line,
    _goal_window_script,
)

ESC = "\x1b"
CR = "\r"

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  \033[32m✓\033[0m {name}")
    else:
        FAIL += 1
        print(f"  \033[31m✗ {name}\033[0m  {detail}")


# --- pure unit checks: keystroke counting contract --------------------------

def unit_checks():
    print("keystroke-counting contract:")
    check("strip :wq", strip_quit(b"ciwHELLO\x1b:wq\r") == b"ciwHELLO\x1b")
    check("count = 9 for ciwHELLO<Esc>", count_keystrokes(b"ciwHELLO\x1b:wq\r") == 9,
          str(count_keystrokes(b"ciwHELLO\x1b:wq\r")))
    check("strip :q for motion", count_keystrokes(b"2w:q\r") == 2,
          str(count_keystrokes(b"2w:q\r")))
    check("strip ZZ", count_keystrokes(b"ddZZ") == 2)
    check("ex command extracted",
          _last_command_line(b":s/a/b/g\r:wq\r") == "s/a/b/g",
          str(_last_command_line(b":s/a/b/g\r:wq\r")))
    check("quit-only -> no command",
          _last_command_line(b"dd:wq\r") is None)
    # escape aliases fold to one Esc so there's no efficiency penalty for them.
    check("jk alias counts as 1 (= par's Esc)",
          count_keystrokes(b"ciwHELLOjk:wq\r", ["jk"]) == 9,
          str(count_keystrokes(b"ciwHELLOjk:wq\r", ["jk"])))
    check("no alias -> jk stays 2 keystrokes",
          count_keystrokes(b"ciwHELLOjk:wq\r") == 10,
          str(count_keystrokes(b"ciwHELLOjk:wq\r")))
    # goal side-pane: buffer drills show the goal buffer; motion drills (no goal
    # buffer) show a "go to the highlighted place" pane keyed off the target.
    buf_pane = _goal_window_script(["alpha", "beta"])
    check("buffer pane shows goal lines",
          "make it look like this" in buf_pane and "alpha" in buf_pane)
    mot_pane = _goal_window_script([], motion_target=(3, 8))
    check("motion pane says go to highlighted place",
          "go to the highlighted place" in mot_pane
          and "line 3, col 8" in mot_pane,
          mot_pane)
    check("motion pane uses :q quit statusline (not :wq save)",
          ":q quit" in mot_pane and ":wq save" not in mot_pane)


# --- integration: one challenge per category, played back through vim -------

def integration_checks():
    print("\nreal-vim playback (one per category):")

    # motion: 2w should land on column 12 (gamma)
    motion = Challenge(start=["alpha beta gamma delta"], start_cursor=[1, 1],
                       target=[1, 12], par_keys=2)
    r = run_attempt(motion, "motion", playback="2w:q\r")
    check("motion lands on target", r.correct, f"cursor={r.final_cursor}")
    check("motion key count == 2", r.keystrokes == 2, str(r.keystrokes))
    check("motion efficiency 1.0", abs(r.efficiency - 1.0) < 1e-9)

    # motion failure: wrong landing
    r = run_attempt(motion, "motion", playback="w:q\r")
    check("motion wrong landing fails", not r.correct, f"cursor={r.final_cursor}")

    # operator: jdd deletes line 2
    op = Challenge(start=["valid line one", "DELETE THIS LINE", "valid line two"],
                   goal=["valid line one", "valid line two"], par_keys=3)
    r = run_attempt(op, "operator", playback="jdd:wq\r")
    check("operator buffer correct", r.correct, str(r.final_buffer))
    check("operator key count == 3", r.keystrokes == 3, str(r.keystrokes))

    # text_object: ci"howdy
    to = Challenge(start=['greeting = "hello"'], goal=['greeting = "howdy"'],
                   par_keys=9)
    r = run_attempt(to, "text_object", playback='ci"howdy\x1b:wq\r')
    check("text_object buffer correct", r.correct, str(r.final_buffer))
    check("text_object key count == 9", r.keystrokes == 9, str(r.keystrokes))

    # register: yank a word and put it — yiw on 'foo', move, replace 'X' with foo
    # start: "foo = X"  -> goal: "foo = foo"
    reg = Challenge(start=["foo = X"], goal=["foo = foo"], par_keys=8)
    # yiw (yank foo), $ to end (on X), ciwfoo? simpler: yiw, then 2W onto X, viwp
    r = run_attempt(reg, "register", playback='yiw$viwp:wq\r')
    check("register buffer correct", r.correct, str(r.final_buffer))

    # macro: uppercase first word of each of 3 lines via a recorded macro
    mac = Challenge(start=["one apple", "two pear", "six plum"],
                    goal=["ONE apple", "TWO pear", "SIX plum"], par_keys=10)
    # qa gUiw j q  then 2@a   (record on line1, replay twice)
    r = run_attempt(mac, "macro", playback="qagUiwj q2@a:wq\r")
    check("macro buffer correct", r.correct, str(r.final_buffer))

    # ex_command: :%normal to append ; — use :%s for determinism
    ex = Challenge(start=["alpha", "beta", "gamma"],
                   goal=["alpha;", "beta;", "gamma;"], par_keys=12)
    r = run_attempt(ex, "ex_command", playback=":%s/$/;/\r:wq\r")
    check("ex_command buffer correct", r.correct, str(r.final_buffer))
    check("ex_command captured command", r.command_line == "%s/$/;/",
          str(r.command_line))

    # search_replace: swap a word everywhere
    sr = Challenge(start=["red car", "red bike", "blue red"],
                   goal=["green car", "green bike", "blue green"], par_keys=16)
    r = run_attempt(sr, "search_replace", playback=":%s/red/green/g\r:wq\r")
    check("search_replace buffer correct", r.correct, str(r.final_buffer))

    # not-saved detection: make the edit but :q! (discard)
    r = run_attempt(op, "operator", playback="jdd:q!\r")
    check("discard (:q!) -> not correct", not r.correct, str(r.final_buffer))
    check("discard flagged not-saved", not r.saved)

    # technique enforcement: a command category must be solved WITH an ex
    # command.  Reaching the same goal by hand-editing (no ':') is rejected even
    # though the buffer matches — otherwise an "ex command" drill teaches nothing.
    rng = Challenge(start=["one", "two", "three", "four"], goal=["four"], par_keys=10)
    r = run_attempt(rng, "ex_command", playback="dddddd:wq\r")   # hand-edit
    check("ex_command hand-edit -> not correct", not r.correct, str(r.command_line))
    r = run_attempt(rng, "ex_command", playback=":1,3d\r:wq\r")  # real command
    check("ex_command via :range passes", r.correct, str(r.command_line))


def main():
    if find_editor() is None:
        print("no vim/nvim on PATH — cannot run integration checks")
        return 1
    print(f"editor: {find_editor()}\n")
    unit_checks()
    integration_checks()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
