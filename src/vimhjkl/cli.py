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
import sys
import time
from functools import partial
from typing import Optional

from . import store, tui
from .challenge import Skill, Challenge, CATEGORIES, is_cursor_category
from .engine import (
    DrillSession, AttemptRecord, SessionSummary,
    select_due_skills, select_weak_skills, mastery_summary, is_due,
    is_grooved, MASTERY_REPS,
    pick_challenge, outcome_passed, attempt_abstained, run_attempt,
    EFFICIENCY_FLOOR,
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
              show_moves: bool = True) -> None:
    if find_editor() is None:
        print(tui.c("No vim or nvim found on PATH — install one, or try "
                    "`--review` for the no-vim flashcards.", tui.RED))
        return
    # Auto-gate new skills by belt rank unless the caller forced one.
    if new_gate is None:
        new_gate = mastery_summary(skills, progress)["new_gate"]
    # Blind mode recalls what you already know — it never introduces brand-new
    # skills.  The pool grows on its own as Learn/Practice/Grind mark skills seen.
    include_new = mode != "blind"
    selected = select_due_skills(skills, progress, count, new_gate=new_gate,
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
                           on_record=lambda: store.save_progress(progress))
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
                 show_moves: bool = True) -> None:
    if find_editor() is None:
        print(tui.c("No vim or nvim found on PATH — install one, or try "
                    "`--review` for the no-vim flashcards.", tui.RED))
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
            result = run_attempt(challenge, skill.category)
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
              new_gate: Optional[int] = None, show_moves: bool = True) -> None:
    """Drill a SINGLE skill ``reps`` times back-to-back, recording every rep, so
    you groove one move into muscle memory in one sitting (depth, vs the breadth
    of a normal session).  Each rep is a fresh random instance of the same skill
    so you learn the technique, not one keystroke sequence.  A quit-without-save
    (abstain) is not penalised and does not burn a rep."""
    if find_editor() is None:
        print(tui.c("No vim or nvim found on PATH — install one, or try "
                    "`--review` for the no-vim flashcards.", tui.RED))
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
        result = run_attempt(challenge, skill.category)
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
}


def _skill_status(skill: Skill, entry: dict, now: float,
                  new_gate: Optional[int]) -> str:
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
                new_gate: Optional[int]) -> str:
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
    btext, bname = _STATUS[_skill_status(skill, entry, now, new_gate)]
    badge = tui.c(btext, getattr(tui, bname))
    return f"  {conf_str} {bar} {reps_str}  {stars}  {title.ljust(28)}  {badge}"


def run_list(skills: list[Skill], progress: dict) -> None:
    now = time.time()
    m = mastery_summary(skills, progress)
    new_gate = m["new_gate"]
    pdata = progress.get("skills", {})

    # Overall accuracy + a count of the active set (so it's clear WHAT repeats).
    total_seen = sum(e.get("seen", 0) for e in pdata.values())
    total_pass = sum(e.get("passes", 0) for e in pdata.values())
    acc_pct = round(100 * total_pass / total_seen) if total_seen else 0
    counts = {k: 0 for k in _STATUS}
    for s in skills:
        counts[_skill_status(s, pdata.get(s.id, {}), now, new_gate)] += 1

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
    for cat in CATEGORIES:
        group = by_cat.get(cat, [])
        if not group:
            continue
        lines.append("")
        lines.append(tui.c(f"  {cat}", tui.BOLD + tui.MAGENTA)
                     + tui.c(f"   ({len(group)} skills)", tui.GREY))
        for s in sorted(group, key=lambda x: (x.difficulty, x.id)):
            lines.append(_skill_line(s, pdata.get(s.id, {}), now, new_gate))

    tui.pager("vimhjkl curriculum", lines,
              subtitle="your confidence, accuracy, and what's queued to repeat",
              header_lines=header)


# ---------------------------------------------------------------------------
# menu / main
# ---------------------------------------------------------------------------

def interactive_menu(skills: list[Skill], progress: dict,
                     show_moves: bool = True) -> None:
    while True:
        choice = tui.menu(
            "vimhjkl — pick up where vimtutor stopped",
            [
                ("learn",    "Learn",      "read the move, then drill it in real vim"),
                ("blind",    "Blind",      "drill from memory — no hints, pure recall"),
                ("practice", "Practice",   "hammer the moves you keep missing, with retries"),
                ("grind",    "Grind",      f"drill ONE skill {DEFAULT_GRIND_REPS}× back-to-back to burn it in"),
                ("review",   "Review",     "no-vim flashcards, away from a good terminal"),
                ("list",     "Curriculum", "your belt, every skill, and its mastery"),
                ("quit",     "Quit",       ""),
            ],
            subtitle="a dojo for the tricks vimtutor never taught you",
            header_lines=_belt_header(skills, progress),
        )
        if choice in (None, "quit"):
            tui.clear()
            print(tui.c("\n  keep your fingers on the home row. ✌\n", tui.CYAN))
            return
        if choice == "learn":
            run_drill(skills, progress, count=10, mode="learn", show_moves=show_moves)
        elif choice == "blind":
            run_drill(skills, progress, count=10, mode="blind", show_moves=show_moves)
        elif choice == "practice":
            run_practice(skills, progress, count=10, show_moves=show_moves)
        elif choice == "grind":
            run_grind(skills, progress, reps=DEFAULT_GRIND_REPS, show_moves=show_moves)
        elif choice == "review":
            run_review(skills, progress, count=10)
        elif choice == "list":
            run_list(skills, progress)


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
    show_moves = not args.hide_moves
    skills = store.load_skills()
    progress = store.load_progress()

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
            run_review(skills, progress, count=args.review)
        elif args.list:
            run_list(skills, progress)
        elif args.reps is not None:
            run_grind(skills, progress, reps=args.reps, new_gate=args.gate,
                      show_moves=show_moves)
        elif args.practice:
            run_practice(skills, progress, count=args.count, show_moves=show_moves)
        elif args.drill:
            run_drill(skills, progress, count=args.count, new_gate=args.gate,
                      mode=args.mode, show_moves=show_moves)
        else:
            interactive_menu(skills, progress, show_moves=show_moves)
    except KeyboardInterrupt:
        # Ctrl-C anywhere closes the app cleanly.  Per-attempt saves already
        # flushed finished work; flush once more defensively, no traceback.
        store.save_progress(progress)
        tui.clear()
        print(tui.c("\n  progress saved. keep your fingers on the home row. ✌\n",
                    tui.CYAN))
    return 0
