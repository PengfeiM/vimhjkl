"""Command-line entry point: menu, drill session, review mode, mastery display.

    python -m vimhjkl                 # interactive menu
    python -m vimhjkl --drill [-n N]  # straight into a live-vim drill
    python -m vimhjkl --review [N]    # no-vim flashcard recall
    python -m vimhjkl --list          # show the curriculum + mastery
"""

from __future__ import annotations

import argparse
import random
import re
import shutil
import sys
import time
from functools import partial
from typing import Optional

from . import store, tui, config
from .challenge import Skill, Challenge, CATEGORIES, is_cursor_category
from .engine import (
    DrillSession, AttemptRecord, SessionSummary,
    select_due_skills, select_weak_skills, mastery_summary, is_due,
    is_grooved, MASTERY_REPS,
    pick_challenge, outcome_passed, attempt_abstained, run_attempt,
    reveal_pane_lines, EFFICIENCY_FLOOR,
)
from .grader import find_editor


# ---------------------------------------------------------------------------
# shared presentation
# ---------------------------------------------------------------------------

_MODE_TAG = {
    "learn":    ("learn", tui.CYAN),
    "blind":    ("blind", tui.MAGENTA),
    "practice": ("practice", tui.YELLOW),
    "grind":    ("grind", tui.GREEN),
}

# A live drill splits the window (edit buffer + goal pane), so it needs a floor
# of room or lines wrap and the goal is hidden.  Below this we warn and let the
# user override for the rest of the process (see `_gate_terminal_size`).
MIN_COLS, MIN_ROWS = 80, 24

# Once the user overrides the size warning, don't nag again for the rest of this
# run.  Process-scoped on purpose: relaunching the trainer re-checks (the
# override is "for this session" only).
_size_override = False


def _gate_terminal_size() -> bool:
    """Return True if it's OK to launch a live-vim session.

    If the terminal is smaller than ``MIN_COLS×MIN_ROWS`` and the user hasn't
    already overridden this session, show a warning: press ``x`` to launch anyway
    (remembered for the rest of this run) or any other key to back out.
    """
    global _size_override
    if _size_override:
        return True
    size = shutil.get_terminal_size((MIN_COLS, MIN_ROWS))
    if size.columns >= MIN_COLS and size.lines >= MIN_ROWS:
        return True
    tui.clear()
    tui.banner("terminal too small", "live drills split the window")
    print(tui.c(f"  your terminal is {size.columns}×{size.lines}; drills want at "
                f"least {MIN_COLS}×{MIN_ROWS}.", tui.YELLOW))
    print(tui.c("  the goal pane sits beside the buffer, so a cramped window wraps "
                "lines", tui.GREY))
    print(tui.c("  and hides the target.  Resize the terminal for the best "
                "experience.", tui.GREY))
    print()
    print(tui.c("  press ", tui.RESET) + tui.c("x", tui.GREEN + tui.BOLD)
          + tui.c(" to launch anyway (this session)", tui.RESET)
          + tui.c("    ·    any other key to go back", tui.GREY))
    print(tui.rule())
    k = tui.read_key()
    if k in ("x", "X"):
        _size_override = True
        return True
    return False


def _rep_prefix(rep: Optional[tuple], rest: str) -> str:
    """Prefix a banner subtitle with 'rep k/N · ' during grind sessions."""
    return f"rep {rep[0]}/{rep[1]} · {rest}" if rep else rest


def _strip_keys_from_title(title: str) -> str:
    """Drop the keystroke parenthetical, e.g. "Delete a whole line (dd)"."""
    return re.sub(r"\s*\([^)]*\)", "", title)


def _render_question(skill: Skill, challenge: Challenge) -> None:
    """Render the task buffers (the "question").  Shared by the task screen and
    the abstain screen, so quitting without saving lets you re-read what was
    asked and try again."""
    if is_cursor_category(skill.category):
        tui.render_buffer(challenge.start, "buffer:", tui.BLUE,
                          cursor=challenge.start_cursor, target=challenge.target)
        if challenge.target:
            print(tui.c("  GOAL: move the cursor onto the", tui.GREEN)
                  + tui.c(" highlighted ", tui.HILITE)
                  + tui.c(f"cell (line {challenge.target[0]}, "
                          f"column {challenge.target[1]}), then quit with ", tui.GREEN)
                  + tui.c(":q", tui.BOLD) + tui.c(".", tui.GREEN))
    else:
        tui.render_buffer(challenge.start, "START — edit this:", tui.BLUE)
        print()
        tui.render_buffer(challenge.goal, "GOAL — make it look like this:", tui.GREEN)
        print()
        print(tui.c("  When the buffer matches the goal, save & quit with ", tui.GREEN)
              + tui.c(":wq", tui.BOLD) + tui.c(".", tui.GREEN))


def _show_task(skill: Skill, challenge: Challenge, mode: str = "learn",
               rep: Optional[tuple] = None) -> None:
    """Present a challenge before launching vim.

    ``learn`` / ``practice`` reveal the technique + the move + why up front
    (read, then do).  ``blind`` shows only the before/after buffers — pure recall.
    ``rep`` is a ``(k, N)`` counter shown during grind sessions.
    """
    tui.clear()
    spec = CATEGORIES.get(skill.category)
    tui.banner(_task_title(skill, mode),
               _rep_prefix(rep, spec.blurb if spec else skill.category))
    _render_task_body(skill, challenge, mode)
    print(tui.rule())
    tui.pause("press any key to launch vim…")


def _task_title(skill: Skill, mode: str) -> str:
    # In Blind mode the parenthetical in many titles spells out the keystrokes
    # (e.g. "Delete a whole line (dd)") — strip it so it isn't a free hint.
    return skill.title if mode != "blind" else _strip_keys_from_title(skill.title)


def _render_task_body(skill: Skill, challenge: Challenge, mode: str) -> None:
    """The full task screen content (below the banner): mode tag, teach, the
    before/after buffers, and — outside Blind — the move/why/hint/par."""
    reveal = mode != "blind"
    tag, tagcol = _MODE_TAG.get(mode, _MODE_TAG["learn"])
    print(tui.c(f"  [{tag} mode]", tagcol + tui.BOLD))
    print()
    if reveal:
        print(tui.c("  " + skill.teach, tui.RESET))
        print()
    _render_question(skill, challenge)
    print()
    if reveal:
        # Read-and-do: show the idiomatic path before the user drills it.
        print(tui.c("  the move:  ", tui.CYAN) + tui.c(challenge.solution, tui.BOLD))
        if challenge.why:
            print(tui.c("  why:       " + challenge.why, tui.GREY))
        if challenge.hint:
            print(tui.c("  hint:      " + challenge.hint, tui.YELLOW))
        print(tui.c(f"  par:       {challenge.par_keys} keystrokes", tui.GREY))
    else:
        print(tui.c("  no hints — recall the move from the before/after alone.",
                    tui.MAGENTA))


def _beat_par_line(r) -> Optional[str]:
    """Congratulate when the player used FEWER keys than the authored par."""
    if r.correct and not r.aborted and 0 < r.keystrokes < r.par_keys:
        return tui.c(f"  ★ you beat par! {r.keystrokes} keys vs {r.par_keys} — "
                     "you found an even shorter path. nice.", tui.GREEN + tui.BOLD)
    return None


def _result_action() -> str:
    """Prompt for what to do after a graded attempt: retry / next / quit."""
    print("  " + tui.c("r", tui.YELLOW) + " retry   "
          + tui.c("n", tui.GREEN) + " next   "
          + tui.c("q", tui.GREY) + " quit")
    while True:
        k = tui.read_key()
        if k in ("r", "R"):
            return "retry"
        if k in ("n", "N", " ", "\r"):
            return "next"
        if k in ("q", "Q"):
            return "quit"


def _abstain_action() -> str:
    """After quitting without saving: any key relaunches the same task; n skips,
    q quits."""
    print(tui.c("  press any key to try again", tui.RESET)
          + tui.c("    ·    n skip    ·    q quit", tui.GREY))
    k = tui.read_key()
    if k in ("n", "N"):
        return "next"
    if k in ("q", "Q"):
        return "quit"
    return "retry"


def _show_result(record: AttemptRecord, show_moves: bool = True,
                 mode: str = "learn", rep: Optional[tuple] = None) -> str:
    r = record.result
    tui.clear()
    if r.aborted:
        tui.banner(record.skill.title, _rep_prefix(rep, "result"))
        print(tui.c("  ⚠ " + (r.message or "vim could not run."), tui.RED))
        tui.pause()
        return "next"
    if record.abstained:
        # Quit without saving: no penalty.  Re-show the FULL task (description,
        # buffers, the move) — the same screen you saw before — then any key
        # relaunches the same task in a fresh buffer.
        tui.banner(_task_title(record.skill, mode),
                   _rep_prefix(rep, "you quit — no penalty · here's the task again"))
        _render_task_body(record.skill, record.challenge, mode)
        print(tui.rule())
        return _abstain_action()
    tui.banner(record.skill.title, _rep_prefix(rep, "result"))
    color = tui.GREEN if r.correct else tui.RED
    print("  " + tui.c(r.stars, color + tui.BOLD))
    beat = _beat_par_line(r)
    if beat:
        print(beat)
    if r.message:
        print(tui.c("  " + r.message, tui.YELLOW))
    if record.passed:
        print(tui.c("  ↑ promoted", tui.GREEN))
    elif not r.correct:
        print(tui.c("  ↓ demoted", tui.RED))
    print()
    # Your own keystrokes, then the optimal path — so you can compare.
    if show_moves and r.keys_typed:
        print(tui.c("  your moves: ", tui.YELLOW) + tui.c(r.keys_typed, tui.BOLD))
    if record.challenge.solution:
        print(tui.c("  optimal:    ", tui.CYAN) + tui.c(record.challenge.solution, tui.BOLD))
    if record.challenge.why:
        print(tui.c("  why:        " + record.challenge.why, tui.GREY))
    if record.skill.key_commands:
        print(tui.c("  keys:       " + "  ".join(record.skill.key_commands), tui.GREY))
    print(tui.rule())
    return _result_action()


# ---------------------------------------------------------------------------
# drill
# ---------------------------------------------------------------------------

def run_drill(skills: list[Skill], progress: dict, count: int,
              new_gate: Optional[int] = None, mode: str = "learn",
              show_moves: bool = True,
              escape_aliases: Optional[list[str]] = None,
              blind_all: bool = False) -> None:
    if find_editor() is None:
        print(tui.c("No vim or nvim found on PATH — install one, or try "
                    "`--review` for the no-vim flashcards.", tui.RED))
        return
    if not _gate_terminal_size():
        return
    # Auto-gate new skills by belt rank unless the caller forced one.
    if new_gate is None:
        new_gate = mastery_summary(skills, progress)["new_gate"]
    # Blind mode defaults to recalling what you already know — it never introduces
    # brand-new skills (the pool grows on its own as Learn/Practice/Grind mark
    # skills seen).  "Blind-all" (cold) opts INTO unseen skills: it bypasses the
    # difficulty gate and a cold miss marks the skill seen, pulling it into normal
    # scheduling.
    cold = mode == "blind" and blind_all
    include_new = mode != "blind" or blind_all
    selected = select_due_skills(skills, progress, count,
                                 new_gate=None if cold else new_gate,
                                 include_new=include_new, rng=random.Random())
    if not selected:
        if not include_new:
            print(tui.c("Nothing to recall yet — play Learn mode first to "
                        "unlock skills for Blind.", tui.YELLOW))
        else:
            print(tui.c("No skills available. Build the curriculum first.", tui.YELLOW))
        return
    present = partial(_show_task, mode=mode)
    review = partial(_show_result, show_moves=show_moves, mode=mode)
    session = DrillSession(skills, progress, present=present, review=review,
                           on_record=lambda: store.save_progress(progress),
                           escape_aliases=escape_aliases,
                           highlight_target=(mode != "blind"),
                           reveal_detail=(mode == "learn"))
    summary = session.run(selected)
    store.save_progress(progress)
    _show_summary(summary, skills, progress, mode=mode)


# ---------------------------------------------------------------------------
# practice (remedial: hammer the skills you keep missing, with retries)
# ---------------------------------------------------------------------------

def _show_practice_result(record: AttemptRecord, show_moves: bool = True,
                          mode: str = "practice") -> str:
    """Show the graded outcome and ask what to do next.

    Returns one of ``"retry"`` / ``"next"`` / ``"quit"``.
    """
    r = record.result
    tui.clear()
    if r.aborted:
        tui.banner(record.skill.title, "practice · result")
        print(tui.c("  ⚠ " + (r.message or "vim could not run."), tui.RED))
        tui.pause()
        return "next"
    if record.abstained:
        # Quit without saving: no penalty.  Re-show the full task, then any key
        # relaunches it in a fresh buffer.
        tui.banner(_task_title(record.skill, mode),
                   "you quit — no penalty · here's the task again")
        _render_task_body(record.skill, record.challenge, mode)
        print(tui.rule())
        return _abstain_action()
    tui.banner(record.skill.title, "practice · result")
    color = tui.GREEN if r.correct else tui.RED
    print("  " + tui.c(r.stars, color + tui.BOLD))
    beat = _beat_par_line(r)
    if beat:
        print(beat)
    if r.message:
        print(tui.c("  " + r.message, tui.YELLOW))
    print()
    if show_moves and r.keys_typed:
        print(tui.c("  your moves: ", tui.YELLOW) + tui.c(r.keys_typed, tui.BOLD))
    if record.challenge.solution:
        print(tui.c("  optimal:    ", tui.CYAN) + tui.c(record.challenge.solution, tui.BOLD))
    if record.challenge.why:
        print(tui.c("  why:        " + record.challenge.why, tui.GREY))
    print(tui.rule())
    good = r.correct and r.efficiency >= EFFICIENCY_FLOOR
    prompt = ("  nailed it — " if good else "  ")
    print(tui.c(prompt
                + tui.c("r", tui.YELLOW) + " retry   "
                + tui.c("n", tui.GREEN) + " next skill   "
                + tui.c("q", tui.GREY) + " quit", tui.RESET))
    while True:
        k = tui.read_key()
        if k in ("r", "R"):
            return "retry"
        if k in ("n", "N", " ", "\r"):
            return "next"
        if k in ("q", "Q", "\x03"):
            return "quit"


def run_practice(skills: list[Skill], progress: dict, count: int,
                 show_moves: bool = True,
                 escape_aliases: Optional[list[str]] = None) -> None:
    if find_editor() is None:
        print(tui.c("No vim or nvim found on PATH — install one, or try "
                    "`--review` for the no-vim flashcards.", tui.RED))
        return
    if not _gate_terminal_size():
        return
    selected = select_weak_skills(skills, progress, count, rng=random.Random())
    if not selected:
        tui.clear()
        tui.banner("practice", "nothing to remediate yet")
        print(tui.c("  Practice hammers the moves you keep missing — but you "
                    "haven't missed any yet.", tui.YELLOW))
        print(tui.c("  Drill (Learn or Blind) first; failed skills show up here.",
                    tui.GREY))
        print(tui.rule())
        tui.pause()
        return

    summary = SessionSummary()
    for skill in selected:
        passed = False
        best_eff = 0.0
        genuine_attempt = False     # at least one real try (not a no-save bail)
        action = "next"
        challenge = pick_challenge(skill)
        present_next = True
        # Retry the skill until the user moves on.  An abstain re-shows the full
        # task itself, so its retry relaunches the SAME buffer (no double-present).
        while True:
            if present_next:
                _show_task(skill, challenge, mode="practice")
            present_next = True
            result = run_attempt(challenge, skill.category,
                                 escape_aliases=escape_aliases,
                                 highlight_target=True,
                                 goal_extra=reveal_pane_lines(skill, challenge))
            abstained = attempt_abstained(result, skill.category)
            if not abstained:
                genuine_attempt = True
            if result.correct:
                passed = True
                best_eff = max(best_eff, result.efficiency)
            record = AttemptRecord(skill, challenge, result, passed, abstained=abstained)
            summary.attempts.append(record)
            action = _show_practice_result(record, show_moves=show_moves)
            if action == "retry":
                if abstained:
                    present_next = False    # abstain screen already showed it
                else:
                    challenge = pick_challenge(skill)
                continue
            break
        # Record ONE Leitner outcome per skill (no double-demotion thrash from
        # rapid retries).  If every try was a quit-without-saving bail, leave the
        # box untouched — promote only on a real solve, demote only on a real miss.
        if genuine_attempt:
            store.record_result(progress, skill.id,
                                passed and best_eff >= EFFICIENCY_FLOOR, best_eff)
            store.save_progress(progress)   # flush after every practiced skill
        if action == "quit":
            break
    _show_summary(summary, skills, progress, mode="practice")


# ---------------------------------------------------------------------------
# grind (depth: drill ONE skill back-to-back to build muscle memory)
# ---------------------------------------------------------------------------

DEFAULT_GRIND_REPS = 6


def run_grind(skills: list[Skill], progress: dict, reps: int,
              new_gate: Optional[int] = None, show_moves: bool = True,
              escape_aliases: Optional[list[str]] = None) -> None:
    """Drill a SINGLE skill ``reps`` times back-to-back, recording every rep, so
    you groove one move into muscle memory in one sitting (depth, vs the breadth
    of a normal session).  Each rep is a fresh random instance of the same skill
    so you learn the technique, not one keystroke sequence.  A quit-without-save
    (abstain) is not penalised and does not burn a rep."""
    if find_editor() is None:
        print(tui.c("No vim or nvim found on PATH — install one, or try "
                    "`--review` for the no-vim flashcards.", tui.RED))
        return
    if not _gate_terminal_size():
        return
    if reps < 1:
        print(tui.c("--reps needs a positive count.", tui.YELLOW))
        return
    if new_gate is None:
        new_gate = mastery_summary(skills, progress)["new_gate"]
    # Grind the single highest-priority skill (weakest / fewest reps / most due).
    top = select_due_skills(skills, progress, 1, new_gate=new_gate,
                            rng=random.Random())
    if not top:
        print(tui.c("No skills available. Build the curriculum first.", tui.YELLOW))
        return
    skill = top[0]

    rng = random.Random()
    summary = SessionSummary()
    done = 0
    action = "next"
    challenge = pick_challenge(skill, rng)
    present_next = True
    while done < reps:
        if present_next:
            _show_task(skill, challenge, mode="grind", rep=(done + 1, reps))
        present_next = True
        result = run_attempt(challenge, skill.category,
                             escape_aliases=escape_aliases,
                             highlight_target=True,
                             goal_extra=reveal_pane_lines(skill, challenge))
        abstained = attempt_abstained(result, skill.category)
        passed = (not abstained) and outcome_passed(result)
        record = AttemptRecord(skill, challenge, result, passed, abstained=abstained)
        action = _show_result(record, show_moves=show_moves, mode="grind",
                              rep=(done + 1, reps))
        if action == "retry":
            if abstained:
                present_next = False        # abstain screen already re-showed it
            else:
                challenge = pick_challenge(skill, rng)
            continue
        if abstained:
            # Bailed without saving: don't count it as a rep or touch mastery.
            if action == "quit":
                break
            challenge = pick_challenge(skill, rng)
            continue
        # A committed rep: record it toward the box + the 25-rep groove target.
        store.record_result(progress, skill.id, passed, result.efficiency)
        store.save_progress(progress)
        summary.attempts.append(record)
        done += 1
        if action == "quit":
            break
        challenge = pick_challenge(skill, rng)
    _show_summary(summary, skills, progress, mode="grind")


def _most_missed_lines(skills: list[Skill], progress: dict,
                       limit: int = 5) -> list[str]:
    """The techniques you fail most — so mistakes are visible, not buried.  Ranked
    by fail count, tie-broken by a recent fail then a low box.  Empty if you have
    not missed anything yet."""
    pdata = progress.get("skills", {})
    missed = []
    for s in skills:
        e = pdata.get(s.id) or {}
        fails = e.get("fails", 0)
        if fails > 0:
            missed.append((s, e, fails))
    if not missed:
        return []
    missed.sort(key=lambda t: (t[2], t[1].get("last_result") == "fail",
                               -t[1].get("box", 1)), reverse=True)
    out = [tui.c("most-missed moves — what trips you up", tui.BOLD + tui.RED)]
    for s, e, fails in missed[:limit]:
        seen = e.get("seen", 0)
        rate = f"{fails}/{seen}" if seen else f"{fails}"
        box = e.get("box", 1)
        flag = tui.c(" ← failed last time", tui.RED) if e.get("last_result") == "fail" else ""
        out.append("  " + tui.c(f"✗ {fails:>2}", tui.RED) + "  "
                   + tui.c(f"{s.title[:34]:<34}", tui.RESET)
                   + tui.c(f"  missed {rate}  · box {box}", tui.GREY) + flag)
    out.append(tui.c("Tip: Practice mode drills exactly these.", tui.YELLOW))
    return out


def _belt_header(skills: list[Skill], progress: dict) -> list[str]:
    """Return the belt/rank lines shown at the top of menus and summaries."""
    m = mastery_summary(skills, progress)
    belt = m["belt"]
    bar = tui.progress_bar(m["fraction"], width=22)
    return [
        tui.c(f"🥋 {belt} belt", tui.BOLD + tui.YELLOW)
        + "   " + bar
        + tui.c(f"  {m['percent']}%", tui.BOLD)
        + tui.c(f"   level {m['level']}/{m['max_level']}", tui.GREY),
        tui.c(f"   {m['mastered']}/{m['total']} skills learned"
              f"  ·  {m['grooved']}/{m['total']} grooved (≥{MASTERY_REPS} reps)"
              f"  ·  new unlock up to ★{m['new_gate']}", tui.GREY),
    ]


def _next_steps(summary: SessionSummary, mode: str) -> list[str]:
    """What to do after a session — so it doesn't just dump you at the menu."""
    misses = summary.total - summary.correct - summary.skipped
    nxt = {
        "learn": "Next: try Blind mode to recall these without the hints.",
        "blind": "Next: keep cycling Blind to lock it in, or Practice your misses.",
        "practice": "Next: Learn or Blind to widen your range.",
        "grind": "Next: come back tomorrow — reps spaced out over days groove it for good.",
    }
    out: list[str] = []
    if misses > 0:
        out.append(tui.c(f"↻ {misses} trick(s) tripped you up — pick Practice "
                         "to drill just those.", tui.YELLOW))
    if mode in nxt:
        out.append(tui.c(nxt[mode], tui.CYAN))
    out.append(tui.c("At the menu: ↑/↓ pick a mode · Enter to start · q to quit.",
                     tui.GREY))
    return out


def _show_summary(summary: SessionSummary, skills: list[Skill],
                  progress: dict, mode: str = "learn") -> None:
    tui.clear()
    tui.banner("session complete", "")
    for line in _belt_header(skills, progress):
        print("  " + line)
    print(tui.rule())
    print(f"  challenges: {summary.total}")
    print("  correct:    " + tui.c(f"{summary.correct}/{summary.total}", tui.GREEN))
    print("  promoted:   " + tui.c(str(summary.promoted), tui.CYAN))
    if summary.skipped:
        print("  skipped:    " + tui.c(str(summary.skipped), tui.GREY))
    print(tui.rule())
    for a in summary.attempts:
        if a.abstained:
            print(f"  {tui.c('–', tui.GREY)} {a.skill.title:<38} "
                  + tui.c("skipped (not saved)", tui.GREY))
            continue
        mark = tui.c("✓", tui.GREEN) if a.result.correct else tui.c("✗", tui.RED)
        eff = f"{int(a.result.efficiency*100)}%" if a.result.correct else "—"
        print(f"  {mark} {a.skill.title:<38} {a.result.keystrokes:>3}/{a.result.par_keys:<3} keys  {eff}")
    print(tui.rule())
    for line in _next_steps(summary, mode):
        print("  " + line)
    print()
    tui.pause("press any key to return to the menu…")


# ---------------------------------------------------------------------------
# review (no-vim flashcards)
# ---------------------------------------------------------------------------

def run_review(skills: list[Skill], progress: dict, count: int) -> None:
    selected = select_due_skills(skills, progress, count, rng=random.Random())
    if not selected:
        print(tui.c("No skills available. Build the curriculum first.", tui.YELLOW))
        return
    seen = promoted = demoted = 0
    for skill in selected:
        challenge = pick_challenge(skill)
        # FRONT
        tui.clear()
        spec = CATEGORIES.get(skill.category)
        tui.banner("review · " + skill.title, spec.blurb if spec else "")
        print(tui.c("  TASK: " + skill.teach, tui.RESET))
        print()
        tui.render_buffer(challenge.start, "before:", tui.BLUE,
                          cursor=challenge.start_cursor,
                          target=challenge.target if is_cursor_category(skill.category) else None)
        if is_cursor_category(skill.category) and challenge.target:
            print(tui.c(f"  → land the cursor on the highlighted cell "
                        f"(line {challenge.target[0]}, col {challenge.target[1]}).",
                        tui.GREY))
        elif challenge.goal:
            print()
            tui.render_buffer(challenge.goal, "after:", tui.GREEN)
        print(tui.rule())
        print(tui.c("  press <space> to flip · q to quit", tui.GREY))
        key = tui.read_key()
        if key in ("q", "\x03"):
            break
        # BACK
        tui.clear()
        tui.banner("review · " + skill.title, "answer")
        sol = challenge.solution or " ".join(skill.key_commands)
        print(tui.c("  command(s): ", tui.CYAN) + tui.c(sol, tui.BOLD))
        print(tui.c(f"  par:        {challenge.par_keys} keystrokes", tui.GREY))
        if skill.key_commands:
            print(tui.c("  family:     " + "  ".join(skill.key_commands), tui.GREY))
        why = challenge.why or challenge.hint
        if why:
            print(tui.c("  why:        " + why, tui.YELLOW))
        print(tui.rule())
        print(tui.c("  rate yourself:  "
                    + tui.c("j", tui.GREEN) + "=got it   "
                    + tui.c("f", tui.RED) + "=fumbled   "
                    + tui.c("k", tui.GREY) + "=skip   "
                    + tui.c("q", tui.GREY) + "=quit", tui.RESET))
        seen += 1
        rate = tui.read_key()
        if rate == "j":
            store.record_result(progress, skill.id, True, 1.0)
            promoted += 1
        elif rate == "f":
            store.record_result(progress, skill.id, False, 0.0)
            demoted += 1
        elif rate in ("q", "\x03"):
            break
        # k / anything else == skip, no change
        store.save_progress(progress)   # flush after every rated card
    store.save_progress(progress)
    tui.clear()
    tui.banner("review complete", "")
    print(f"  cards seen: {seen}")
    print("  promoted:   " + tui.c(str(promoted), tui.GREEN))
    print("  demoted:    " + tui.c(str(demoted), tui.RED))
    print()


# ---------------------------------------------------------------------------
# list / mastery
# ---------------------------------------------------------------------------

# status of a skill in the spaced-repetition schedule (why it does/doesn't recur)
_STATUS = {
    "due":      ("● due",       "YELLOW"),   # low confidence / interval elapsed -> repeats next
    "new":      ("○ new",       "CYAN"),     # unlocked, waiting to be introduced
    "grooved":  ("✦ grooved",   "GREEN"),    # box 5 AND drilled to the rep target -> maintenance
    "learned":  ("★ learned",   "GREEN"),    # box 5: you know the move, still racking up reps
    "resting":  ("· resting",   "GREY"),     # solid for now, will resurface later
    "locked":   ("· locked",    "GREY"),     # above your current unlock level
    "off":      ("✕ off",       "GREY"),     # switched off in Settings -> never scheduled
}


def _skill_status(skill: Skill, entry: dict, now: float,
                  new_gate: Optional[int], disabled: bool = False) -> str:
    if disabled:
        return "off"
    if not entry.get("last_seen", 0.0):
        if new_gate is None or skill.difficulty <= new_gate:
            return "new"
        return "locked"
    # Two axes: box 5 == "you know the move" (★ learned); drilled to the rep
    # target on top of that == "grooved", now on the rare maintenance schedule.
    # Both still resurface in drills — showing them as "due" next to skills
    # you're failing was just confusing.
    if is_grooved(entry):
        return "grooved"
    if entry.get("box", 1) >= 5:
        return "learned"
    if is_due(entry, now):
        return "due"
    return "resting"


def _confidence(entry: dict) -> float:
    """Mastery as a 0–1 confidence (from the Leitner box 1..5)."""
    return (entry.get("box", 1) - 1) / 4


def _conf_color(conf: float) -> str:
    return tui.RED if conf < 0.34 else (tui.YELLOW if conf < 0.67 else tui.GREEN)


def _skill_line(skill: Skill, entry: dict, now: float,
                new_gate: Optional[int], disabled: bool = False) -> str:
    conf = _confidence(entry)
    ccol = _conf_color(conf)
    conf_str = tui.c(f"{conf:.2f}", ccol)
    bar = tui.progress_bar(conf, width=6, color=ccol)
    # Reps toward the muscle-memory target (axis 2), capped at the target.
    reps = entry.get("passes", 0)
    if not entry.get("last_seen", 0.0):
        reps_str = tui.c("  —  ", tui.GREY)
    else:
        rcol = tui.GREEN if reps >= MASTERY_REPS else tui.GREY
        reps_str = tui.c(f"{min(reps, MASTERY_REPS):>2}/{MASTERY_REPS}", rcol)
    stars = tui.c("★" * skill.difficulty + "☆" * (5 - skill.difficulty), tui.YELLOW)
    title = skill.title if len(skill.title) <= 28 else skill.title[:27] + "…"
    btext, bname = _STATUS[_skill_status(skill, entry, now, new_gate, disabled)]
    badge = tui.c(btext, getattr(tui, bname))
    return f"  {conf_str} {bar} {reps_str}  {stars}  {title.ljust(28)}  {badge}"


def run_list(skills: list[Skill], progress: dict, cfg: Optional[dict] = None) -> None:
    now = time.time()
    cfg = cfg if cfg is not None else config.load()
    off = config.disabled_set(cfg)
    # Belt/mastery reflect only the lessons in play (disabled ones excluded), but
    # the list itself shows everything so off lessons stay visible/re-enableable.
    m = mastery_summary([s for s in skills if s.id not in off], progress)
    new_gate = m["new_gate"]
    pdata = progress.get("skills", {})

    # Overall accuracy + a count of the active set (so it's clear WHAT repeats).
    total_seen = sum(e.get("seen", 0) for e in pdata.values())
    total_pass = sum(e.get("passes", 0) for e in pdata.values())
    acc_pct = round(100 * total_pass / total_seen) if total_seen else 0
    counts = {k: 0 for k in _STATUS}
    for s in skills:
        counts[_skill_status(s, pdata.get(s.id, {}), now, new_gate,
                             s.id in off)] += 1

    header = _belt_header(skills, progress)
    header.append(
        tui.c(f"accuracy {acc_pct}% over {total_seen} attempts", tui.GREY)
        + tui.c(f"   ·   {counts['due']} due now · {counts['new']} new "
                f"· {counts['grooved']} grooved · {counts['locked']} locked", tui.GREY))
    header.append(
        tui.c("● due", tui.YELLOW) + "  " + tui.c("○ new", tui.CYAN) + "  "
        + tui.c("★ learned", tui.GREEN) + "  " + tui.c("✦ grooved", tui.GREEN) + "  "
        + tui.c("· resting/locked", tui.GREY)
        + tui.c(f"   — reps count toward {MASTERY_REPS}, then rest", tui.GREY))

    by_cat: dict[str, list[Skill]] = {}
    for s in skills:
        by_cat.setdefault(s.category, []).append(s)

    lines: list[str] = []
    missed = _most_missed_lines(skills, progress)
    if missed:
        lines += missed + [""]
    for cat in CATEGORIES:
        group = by_cat.get(cat, [])
        if not group:
            continue
        lines.append("")
        lines.append(tui.c(f"  {cat}", tui.BOLD + tui.MAGENTA)
                     + tui.c(f"   ({len(group)} skills)", tui.GREY))
        for s in sorted(group, key=lambda x: (x.difficulty, x.id)):
            lines.append(_skill_line(s, pdata.get(s.id, {}), now, new_gate,
                                     s.id in off))

    tui.pager("vimhjkl curriculum", lines,
              subtitle="your confidence, accuracy, and what's queued to repeat",
              header_lines=header)


# ---------------------------------------------------------------------------
# settings — lessons on/off + escape-key aliases (config.json, not progress)
# ---------------------------------------------------------------------------

def _lesson_rows(skills: list[Skill], cfg: dict) -> list[dict]:
    """Flatten the curriculum into selectable rows for the toggle page: a header
    row per category (toggles the whole group) followed by its skills.  Skill rows
    carry the teach text + key_commands so the detail panel can describe them."""
    by_cat: dict[str, list[Skill]] = {}
    for s in skills:
        by_cat.setdefault(s.category, []).append(s)
    rows: list[dict] = []
    for cat in CATEGORIES:
        group = by_cat.get(cat, [])
        if not group:
            continue
        ids = [s.id for s in group]
        on = sum(1 for s in group if not config.is_disabled(cfg, s.id))
        spec = CATEGORIES.get(cat)
        rows.append({"kind": "cat", "cat": cat, "ids": ids, "on": on,
                     "total": len(group), "blurb": spec.blurb if spec else ""})
        for s in sorted(group, key=lambda x: (x.difficulty, x.id)):
            rows.append({"kind": "skill", "id": s.id, "title": s.title,
                         "diff": s.difficulty, "category": s.category,
                         "teach": s.teach, "keys": s.key_commands,
                         "enabled": not config.is_disabled(cfg, s.id)})
    return rows


# A state slider sized and drawn like the curriculum confidence bar (width 6, same
# ▓/░ blocks as tui.progress_bar): a coloured knob block sits at the matching
# position — LEFT + red = off, MIDDLE + yellow = partly on, RIGHT + green = on.
_SWITCH_W = 7      # curriculum bar is 6; +10% rounds up to 7
_KNOB_W = 3        # the coloured knob block (wider than a single cell)
_SWITCH_COLOR = {"off": tui.RED, "partial": tui.YELLOW, "on": tui.GREEN}


def _switch(state: str) -> str:
    color = _SWITCH_COLOR[state]
    # Slide the knob block to the LEFT (off), MIDDLE (partial) or RIGHT (on).
    start = {"off": 0,
             "partial": (_SWITCH_W - _KNOB_W) // 2,
             "on": _SWITCH_W - _KNOB_W}[state]
    return "".join(
        tui.c("▓", color + tui.BOLD) if start <= i < start + _KNOB_W
        else tui.c("░", tui.GREY)
        for i in range(_SWITCH_W)
    )


def _lesson_row_text(row: dict, selected: bool, title_max: int = 40) -> str:
    pointer = tui.c(" ▸ ", tui.CYAN + tui.BOLD) if selected else "   "
    if row["kind"] == "cat":
        state = ("on" if row["on"] == row["total"]
                 else "off" if row["on"] == 0 else "partial")
        label = tui.c(row["cat"], tui.BOLD + tui.MAGENTA)
        tail = tui.c(f"  ({row['on']}/{row['total']} on)", tui.GREY)
        return pointer + _switch(state) + " " + label + tail
    sw = _switch("on" if row["enabled"] else "off")
    stars = tui.c("★" * row["diff"], tui.YELLOW)
    title = row["title"] if len(row["title"]) <= title_max else row["title"][:title_max - 1] + "…"
    col = tui.RESET if row["enabled"] else tui.GREY
    return pointer + "  " + sw + "   " + tui.c(title, col) + "  " + stars


def _lesson_match_indices(rows: list[dict], query: str) -> list[int]:
    """Row indices matching a ``/`` search — case-insensitive substring over a
    lesson's title + its keys (or a category's name)."""
    q = query.lower().strip()
    if not q:
        return []
    out = []
    for i, r in enumerate(rows):
        if r["kind"] == "skill":
            hay = (r["title"] + " " + " ".join(r.get("keys", []))).lower()
        else:
            hay = r["cat"].lower()
        if q in hay:
            out.append(i)
    return out


def _lesson_detail_lines(row: dict, width: int) -> list[str]:
    """The side panel describing the highlighted row: a category's purpose, or a
    skill's keys + what it teaches.  Plain wrapped to ``width`` columns."""
    out: list[str] = []
    if row["kind"] == "cat":
        out.append(tui.c(row["cat"], tui.BOLD + tui.MAGENTA))
        out.append(tui.c(f"{row['on']}/{row['total']} lessons on", tui.GREY))
        out.append("")
        for ln in tui.wrap_plain(row["blurb"], width):
            out.append(tui.c(ln, tui.RESET))
        out.append("")
        out.append(tui.c("space toggles the whole group.", tui.YELLOW))
        return out
    out.append(tui.c(row["title"], tui.BOLD + tui.CYAN))
    diff = row["diff"]
    out.append(tui.c("★" * diff + "☆" * (5 - diff), tui.YELLOW)
               + tui.c(f"  difficulty {diff}/5", tui.GREY))
    out.append(tui.c(("● enabled" if row["enabled"] else "✕ off — skipped"),
                     tui.GREEN if row["enabled"] else tui.GREY))
    out.append("")
    if row["keys"]:
        out.append(tui.c("keys", tui.BOLD))
        for ln in tui.wrap_plain("  ".join(row["keys"]), width):
            out.append(tui.c(ln, tui.YELLOW))
        out.append("")
    out.append(tui.c("what it is", tui.BOLD))
    for ln in tui.wrap_plain(row["teach"], width):
        out.append(tui.c(ln, tui.GREY))
    return out


def run_lessons(skills: list[Skill], cfg: dict) -> None:
    """Apple-Settings-style on/off page: toggle individual lessons or a whole
    category.  Disabled lessons are excluded from every session (and the belt
    maths) but stay listed here so they can be switched back on."""
    if not skills:
        tui.clear()
        tui.banner("lessons", "nothing to configure")
        print(tui.c("  No curriculum loaded.", tui.YELLOW))
        tui.pause()
        return
    state = {"sel": 0, "top": 0, "count": "", "g": False,
             "searching": False, "query": "", "search_start": 0}

    def render() -> str:
        rows = _lesson_rows(skills, cfg)
        n = len(rows)
        state["sel"] = max(0, min(state["sel"], n - 1))
        size = shutil.get_terminal_size((80, 24))
        cols, lines = size.columns, size.lines
        view_h = max(6, lines - 10)
        # Insert a blank SEPARATOR before each category so the groups read as
        # distinct elements with a gap between them.  Separators are visual only —
        # NOT in `rows` — so selection/toggle/navigation are unaffected, and the
        # cursor + rnu gutter stay in lesson units (one j = one lesson, gaps
        # skipped).  `display` entries are a row index, or None for a gap line.
        display: list = []
        for i, r in enumerate(rows):
            if r["kind"] == "cat" and display:
                display.append(None)
            display.append(i)
        dn = len(display)
        sel_disp = display.index(state["sel"])
        # keep the cursor inside the window (in display-line units)
        if sel_disp < state["top"]:
            state["top"] = sel_disp
        elif sel_disp >= state["top"] + view_h:
            state["top"] = sel_disp - view_h + 1
        state["top"] = max(0, min(state["top"], max(0, dn - view_h)))

        # Two columns with a clear boundary: the lesson list on the left, a detail
        # panel on the right.  BOTH columns are width-capped and every cell is
        # truncated to its column, so no line can ever exceed the terminal and wrap
        # onto a second row (which is what made the frame grow and 'jump').  The
        # gap is a padded vertical rule so the boundary actually reads as one.
        gap = "   " + tui.c("│", tui.GREY) + "   "      # 7 visible columns
        gap_w = 7
        if cols >= 84:
            left_w = min(58, cols - 28 - gap_w)
            side_w = min(42, cols - left_w - gap_w)
            if side_w < 26:                            # not enough room -> no panel
                side_w, left_w = 0, min(76, cols - 4)
        else:
            side_w, left_w = 0, min(76, cols - 4)
        # Row = rnu gutter (3) + prefix (margin+pointer+switch+gaps) + title + 2 +
        # up to 5 stars; cap the title so the longest row never overflows the
        # divider.
        title_max = max(14, left_w - 27)

        detail = _lesson_detail_lines(rows[state["sel"]], side_w) if side_w else []

        body: list[str] = []
        for k in range(view_h):
            di = state["top"] + k
            if di < dn and display[di] is not None:
                i = display[di]
                left = ("  " + tui.rnu_gutter(i, state["sel"], i == state["sel"])
                        + _lesson_row_text(rows[i], i == state["sel"], title_max))
            else:
                left = ""        # separator gap or past the end of the list
            left = tui.pad_visible(tui.truncate_visible(left, left_w), left_w)
            if side_w:
                right = tui.truncate_visible(detail[k] if k < len(detail) else "",
                                             side_w)
                body.append(left + gap + right)
            else:
                body.append(left)

        off_n = len(config.disabled_set(cfg))
        head = [
            tui.c(f"{len(skills) - off_n} of {len(skills)} lessons on", tui.GREEN)
            + tui.c(f"   ·   {off_n} off (skipped in every mode)", tui.GREY),
            tui.c("★ = difficulty (1–5)", tui.YELLOW)
            + tui.c("   ·   ", tui.GREY) + _switch("on") + tui.c(" on  ", tui.GREY)
            + _switch("off") + tui.c(" off  ", tui.GREY)
            + _switch("partial") + tui.c(" part  ·  a category row toggles all",
                                         tui.GREY),
        ]
        out = ["", tui.c("  ⚔  lessons — what to drill", tui.BOLD + tui.CYAN),
               tui.c("     turn techniques on/off; off ones never appear", tui.GREY),
               tui.rule()]
        out += ["  " + h for h in head]
        out += [tui.rule()] + body + [tui.rule()]
        if state["searching"]:
            matches = _lesson_match_indices(_lesson_rows(skills, cfg), state["query"])
            hits = (tui.c(f"   ({len(matches)} match)", tui.GREEN) if matches
                    else tui.c("   (no match)", tui.RED) if state["query"] else "")
            out.append(tui.c("  /", tui.CYAN + tui.BOLD)
                       + tui.c(state["query"] + "█", tui.BOLD) + hits
                       + tui.c("    Enter keep · Esc cancel", tui.GREY))
        else:
            foot = tui.c("  j/k move · / search · gg/G ends · space toggle · q back",
                         tui.GREY)
            if state["count"]:
                foot += tui.c(f"   {state['count']}", tui.YELLOW + tui.BOLD)
            out.append(foot)
        # Belt-and-braces: no rendered line may exceed the terminal width, or it
        # wraps and the frame 'jumps' on the next redraw.
        out = [tui.truncate_visible(line, cols) for line in out]
        return "\033[2J\033[H" + "\r\n".join(out) + "\r\n"

    def on_key(k: str) -> Optional[str]:
        rows = _lesson_rows(skills, cfg)
        n = len(rows)
        # --- incremental / search mode -----------------------------------
        if state["searching"]:
            if k == "ENTER":             # keep the match, leave search mode
                state["searching"] = False
            elif k == "ESC":             # cancel -> back to where we started
                state["searching"] = False
                state["sel"] = state["search_start"]
                state["query"] = ""
            elif k in ("\x7f", "\x08"):  # backspace
                state["query"] = state["query"][:-1]
            elif len(k) == 1 and k.isprintable():
                state["query"] += k
            m = _lesson_match_indices(rows, state["query"])
            if m:                        # jump to the first match as you type
                state["sel"] = m[0]
            return None
        if k == "/":                     # open search
            state.update(searching=True, query="", search_start=state["sel"])
            return None
        if k in ("n", "N") and state["query"]:   # cycle matches
            m = _lesson_match_indices(rows, state["query"])
            if m:
                if k == "n":
                    state["sel"] = next((i for i in m if i > state["sel"]), m[0])
                else:
                    state["sel"] = next((i for i in reversed(m)
                                         if i < state["sel"]), m[-1])
            return None
        # --- normal navigation -------------------------------------------
        if k.isdigit():
            state["count"] += k          # build a vim count for the next motion
            state["g"] = False
            return None
        if k == "g":                     # gg -> top
            if state["g"]:
                state["sel"], state["g"] = 0, False
            else:
                state["g"] = True
                return None
        elif k in ("UP", "k", "DOWN", "j", "G"):
            state["sel"] = tui._count_move(state["sel"], n, k, state["count"])
        elif k in ("ENTER", " "):
            row = rows[state["sel"]]
            if row["kind"] == "cat":
                all_on = row["on"] == row["total"]
                config.set_many_disabled(cfg, row["ids"], disabled=all_on)
            else:
                config.set_disabled(cfg, row["id"], disabled=row["enabled"])
            config.save(cfg)
        elif k in ("ESC", "q", "Q"):
            return "exit"
        state["count"], state["g"] = "", False
        return None

    tui.live_view(render, on_key)


def run_escape_aliases(cfg: dict) -> None:
    """Configure insert-mode escape aliases (e.g. jk -> <Esc>).  Plain prompt:
    the value is just a short list of letter aliases."""
    tui.clear()
    tui.banner("escape keys", "map a key sequence to <Esc> in drills")
    cur = config.escape_aliases(cfg)
    print(tui.c("  Insert-mode aliases that leave Insert mode, e.g. ", tui.RESET)
          + tui.c("jk", tui.BOLD) + tui.c(" or ", tui.RESET) + tui.c("jj", tui.BOLD)
          + tui.c(".", tui.RESET))
    print(tui.c("  They apply only inside live drills (not the menu).", tui.GREY))
    print(tui.c("  Your alias counts as ONE keystroke (same as <Esc>) — no "
                "efficiency penalty for using it.", tui.GREEN))
    print()
    print(tui.c("  current: ", tui.CYAN)
          + (tui.c("  ".join(cur), tui.BOLD) if cur else tui.c("(none)", tui.GREY)))
    print(tui.rule())
    raw = tui.prompt_line("aliases (space/comma separated, blank to clear, "
                          "Enter keeps current): ")
    if raw.strip() == "":
        return
    aliases = [a for a in re.split(r"[\s,]+", raw.strip()) if a]
    valid = [a for a in aliases if a.isalpha() and 1 <= len(a) <= 3]
    config.set_escape_aliases(cfg, valid)
    config.save(cfg)
    rejected = [a for a in aliases if a not in valid]
    tui.clear()
    tui.banner("escape keys", "saved")
    saved = config.escape_aliases(cfg)
    print(tui.c("  now active: ", tui.GREEN)
          + (tui.c("  ".join(saved), tui.BOLD) if saved else tui.c("(none)", tui.GREY)))
    if rejected:
        print(tui.c("  ignored (letters only, 1–3 chars): " + " ".join(rejected),
                    tui.YELLOW))
    print(tui.rule())
    tui.pause()


def run_settings(skills: list[Skill], cfg: dict) -> None:
    while True:
        off_n = len(config.disabled_set(cfg))
        aliases = config.escape_aliases(cfg)
        choice = tui.menu(
            "settings",
            [
                ("lessons", "Lessons on/off",
                 f"{len(skills) - off_n}/{len(skills)} on — pick what to drill"),
                ("escape", "Escape keys",
                 ("aliases: " + " ".join(aliases)) if aliases
                 else "map jk/jj to <Esc> in drills"),
                ("back", "Back", ""),
            ],
            subtitle="tune the trainer to your setup",
        )
        if choice in (None, "back"):
            return
        if choice == "lessons":
            run_lessons(skills, cfg)
        elif choice == "escape":
            run_escape_aliases(cfg)


# ---------------------------------------------------------------------------
# menu / main
# ---------------------------------------------------------------------------

def _blind_is_cold(enabled: list[Skill]) -> Optional[bool]:
    """Ask which Blind flavour to run: recall-known vs cold blind-all.  Returns
    True for cold, False for recall, or None if cancelled."""
    pick = tui.menu(
        "blind — choose your challenge",
        [
            ("recall", "Recall what you know",
             "only skills you've already been taught — pure memory"),
            ("cold", "Blind-all (cold)",
             "throw ANY skill at you, even ones you've never seen"),
        ],
        subtitle="cold mode ignores the difficulty gate; a cold miss counts as seen",
    )
    if pick is None:
        return None
    return pick == "cold"


def interactive_menu(skills: list[Skill], progress: dict, cfg: dict,
                     show_moves: bool = True) -> None:
    while True:
        # SINGLE filter point: schedule (and rank) only enabled lessons, so a
        # switched-off skill never appears AND never drags the belt down.  The
        # full list still feeds the curriculum + settings views.
        enabled = config.enabled_skills(skills, cfg)
        aliases = config.escape_aliases(cfg)
        choice = tui.menu(
            "vimhjkl — pick up where vimtutor stopped",
            [
                ("learn",    "Learn",      "read the move, then drill it in real vim"),
                ("blind",    "Blind",      "drill from memory — no hints, pure recall"),
                ("practice", "Practice",   "hammer the moves you keep missing, with retries"),
                ("grind",    "Grind",      f"drill ONE skill {DEFAULT_GRIND_REPS}× back-to-back to burn it in"),
                ("review",   "Review",     "no-vim flashcards, away from a good terminal"),
                ("list",     "Curriculum", "your belt, every skill, and its mastery"),
                ("settings", "Settings",   "lessons on/off, escape-key aliases"),
                ("quit",     "Quit",       ""),
            ],
            subtitle="a dojo for the tricks vimtutor never taught you",
            header_lines=_belt_header(enabled, progress),
        )
        if choice in (None, "quit"):
            tui.clear()
            print(tui.c("\n  keep your fingers on the home row. ✌\n", tui.CYAN))
            return
        if choice == "learn":
            run_drill(enabled, progress, count=10, mode="learn",
                      show_moves=show_moves, escape_aliases=aliases)
        elif choice == "blind":
            cold = _blind_is_cold(enabled)
            if cold is None:
                continue
            run_drill(enabled, progress, count=10, mode="blind",
                      show_moves=show_moves, escape_aliases=aliases, blind_all=cold)
        elif choice == "practice":
            run_practice(enabled, progress, count=10, show_moves=show_moves,
                         escape_aliases=aliases)
        elif choice == "grind":
            run_grind(enabled, progress, reps=DEFAULT_GRIND_REPS,
                      show_moves=show_moves, escape_aliases=aliases)
        elif choice == "review":
            run_review(enabled, progress, count=10)
        elif choice == "list":
            run_list(skills, progress, cfg)
        elif choice == "settings":
            run_settings(skills, cfg)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vimhjkl",
        description="A terminal vim-technique trainer that drills advanced moves "
                    "in real vim and grades your keystrokes.",
    )
    p.add_argument("--drill", action="store_true",
                   help="go straight into a live-vim drill session")
    p.add_argument("--mode", choices=("learn", "blind"), default="learn",
                   help="drill mode for --drill: learn (read the move first) "
                        "or blind (no hints). Default: learn")
    p.add_argument("--blind-all", action="store_true",
                   help="with --mode blind: go cold — include skills you've never "
                        "seen (ignores the difficulty gate)")
    p.add_argument("--practice", action="store_true",
                   help="remedial session: retry the skills you keep missing")
    p.add_argument("--reps", nargs="?", const=DEFAULT_GRIND_REPS, type=int,
                   metavar="N",
                   help="grind ONE skill N times back-to-back to build muscle "
                        f"memory (default {DEFAULT_GRIND_REPS})")
    p.add_argument("--review", nargs="?", const=10, type=int, metavar="N",
                   help="no-vim flashcard recall (default 10 cards)")
    p.add_argument("--list", action="store_true",
                   help="print the curriculum and your mastery")
    p.add_argument("-n", "--count", type=int, default=10,
                   help="number of challenges in a drill session (default 10)")
    p.add_argument("--gate", type=int, default=None, metavar="D",
                   help="only introduce new skills of difficulty <= D")
    p.add_argument("--hide-moves", action="store_true",
                   help="don't show your own keystrokes on the result screen")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    tui.install_signal_guard()
    show_moves = not args.hide_moves
    skills = store.load_skills()
    progress = store.load_progress()
    cfg = config.load()
    # Single filter point for CLI-flag sessions too: drill only enabled lessons.
    enabled = config.enabled_skills(skills, cfg)
    aliases = config.escape_aliases(cfg)

    problems = [p for s in skills for p in s.validate()]
    if problems:
        print(tui.c("⚠ curriculum validation issues:", tui.YELLOW), file=sys.stderr)
        for prob in problems[:20]:
            print("   " + prob, file=sys.stderr)

    if not skills:
        print(tui.c("No skills loaded yet — the bundled curriculum is missing. "
                    "Reinstall vimhjkl, or run the build from a source checkout.",
                    tui.YELLOW))
        # Still allow the menu to show for --list etc.

    try:
        if args.review is not None:
            run_review(enabled, progress, count=args.review)
        elif args.list:
            run_list(skills, progress, cfg)
        elif args.reps is not None:
            run_grind(enabled, progress, reps=args.reps, new_gate=args.gate,
                      show_moves=show_moves, escape_aliases=aliases)
        elif args.practice:
            run_practice(enabled, progress, count=args.count, show_moves=show_moves,
                         escape_aliases=aliases)
        elif args.drill:
            run_drill(enabled, progress, count=args.count, new_gate=args.gate,
                      mode=args.mode, show_moves=show_moves, escape_aliases=aliases,
                      blind_all=args.blind_all)
        else:
            interactive_menu(skills, progress, cfg, show_moves=show_moves)
    except KeyboardInterrupt:
        # Ctrl-C anywhere closes the app cleanly.  Per-attempt saves already
        # flushed finished work; flush once more defensively, no traceback.
        store.save_progress(progress)
        tui.clear()
        print(tui.c("\n  progress saved. keep your fingers on the home row. ✌\n",
                    tui.CYAN))
    return 0
