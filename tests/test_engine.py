"""Unit checks for the engine selector + Leitner progress (no vim needed)."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vimhjkl.challenge import Skill, Challenge
from vimhjkl.engine import select_due_skills, is_due, outcome_passed
from vimhjkl.grader import GradeResult
from vimhjkl import store

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  \033[32m✓\033[0m {name}")
    else:
        FAIL += 1
        print(f"  \033[31m✗ {name}\033[0m  {detail}")


def mk(id, diff):
    return Skill(id=id, title=id, category="operator", teach="t",
                 difficulty=diff, challenges=[Challenge(start=["x"], goal=["y"], par_keys=1)])


def main():
    now = time.time()
    skills = [mk("a", 1), mk("b", 3), mk("c", 5), mk("d", 2)]

    # Empty progress -> all "new", gated by difficulty, easiest first.
    prog = {"skills": {}}
    sel = select_due_skills(skills, prog, count=2, new_gate=2, now=now)
    check("gate excludes hard new skills",
          all(s.difficulty <= 2 for s in sel), [s.id for s in sel])
    check("new skills easiest-first", [s.id for s in sel] == ["a", "d"],
          [s.id for s in sel])

    # A seen, failed, box-1 skill should outrank new skills.
    prog = {"skills": {
        "b": {"box": 1, "seen": 3, "passes": 0, "fails": 3,
              "last_seen": now - 1000, "last_result": "fail", "best_efficiency": 0.0},
        "c": {"box": 4, "seen": 5, "passes": 5, "fails": 0,
              "last_seen": now - 5, "last_result": "pass", "best_efficiency": 1.0},
    }}
    sel = select_due_skills(skills, prog, count=4, new_gate=5, now=now)
    check("most-failing due skill comes first", sel[0].id == "b", [s.id for s in sel])
    check("box-4 not-yet-due skill is deprioritised",
          sel[-1].id == "c", [s.id for s in sel])

    # is_due: box 4 rests 600s.
    check("box4 not due after 5s",
          not is_due({"box": 4, "last_seen": now - 5}, now))
    check("box4 due after 700s",
          is_due({"box": 4, "last_seen": now - 700}, now))
    check("never-seen always due", is_due({"box": 1, "last_seen": 0.0}, now))

    # --- Two-axis (rep grooming) regression guards -------------------------
    # New skills must still surface even when many seen skills are due — the
    # box-based tier split (not a reps-based one) is what guarantees this.
    prog_busy = {"skills": {
        s.id: {"box": 5, "seen": 6, "passes": 6, "fails": 0,
               "last_seen": now - 99999, "last_result": "pass",
               "best_efficiency": 1.0}
        for s in [mk("s%d" % i, 2) for i in range(8)]
    }}
    busy_skills = [mk("s%d" % i, 2) for i in range(8)] + [mk("fresh", 2)]
    sel = select_due_skills(busy_skills, prog_busy, count=10, new_gate=5, now=now)
    check("new skill still appears past a pile of due reviews",
          "fresh" in [s.id for s in sel], [s.id for s in sel])

    # A session must BLEND new with old review, not exhaust one side: with many
    # new skills available, a capped session should still include old practice.
    many_new = [mk("n%d" % i, 2) for i in range(20)]
    prog_old = {"skills": {
        "s%d" % i: {"box": 5, "seen": 6, "passes": 6, "fails": 0,
                    "last_seen": now - 99999, "last_result": "pass",
                    "best_efficiency": 1.0}
        for i in range(8)}}
    blend = select_due_skills([mk("s%d" % i, 2) for i in range(8)] + many_new,
                              prog_old, count=10, new_gate=5, now=now)
    ids = [s.id for s in blend]
    check("session blends new + old practice (not all new)",
          any(i.startswith("n") for i in ids) and any(i.startswith("s") for i in ids),
          ids)

    # A grooved skill (box-maxed AND >=25 reps) rests on the long maintenance
    # schedule, so it is NOT due right after being seen...
    grooved = {"box": 5, "passes": 30, "last_seen": now - 10}
    check("grooved skill not due right after seen", not is_due(grooved, now))
    # ...but a later fail drops the box, pulling it out of maintenance and back
    # into frequent review even though its lifetime pass count stays high.
    fumbled = {"box": 4, "passes": 30, "last_seen": now - 700}
    check("fumbled-once grooved skill returns to active review",
          is_due(fumbled, now))

    # Leitner record_result promotes/demotes within [1,5].
    p = {"skills": {}}
    for _ in range(7):
        store.record_result(p, "z", True, 1.0)
    check("box caps at 5", p["skills"]["z"]["box"] == 5, p["skills"]["z"]["box"])
    for _ in range(7):
        store.record_result(p, "z", False, 0.0)
    check("box floors at 1", p["skills"]["z"]["box"] == 1, p["skills"]["z"]["box"])

    # outcome_passed needs correct AND efficient.
    r_ok = GradeResult(True, 2, 2, 1.0, [], None, None, True, False)
    r_sloppy = GradeResult(True, 20, 2, 0.1, [], None, None, True, False)
    r_wrong = GradeResult(False, 2, 2, 1.0, [], None, None, True, False)
    check("efficient correct passes", outcome_passed(r_ok))
    check("sloppy correct does not promote", not outcome_passed(r_sloppy))
    check("wrong never passes", not outcome_passed(r_wrong))

    # --- config: lesson toggle filter + escape-alias validation ------------
    from vimhjkl import config
    cfg = config._default()
    cfg_skills = [mk("a", 1), mk("b", 2), mk("c", 3)]
    check("all enabled by default",
          len(config.enabled_skills(cfg_skills, cfg)) == 3)
    config.set_disabled(cfg, "b", True)
    en = config.enabled_skills(cfg_skills, cfg)
    check("disabled skill filtered out",
          [s.id for s in en] == ["a", "c"], [s.id for s in en])
    config.set_disabled(cfg, "b", False)
    check("re-enable restores skill",
          len(config.enabled_skills(cfg_skills, cfg)) == 3)
    config.set_many_disabled(cfg, ["a", "c"], True)
    check("category-style bulk disable",
          [s.id for s in config.enabled_skills(cfg_skills, cfg)] == ["b"])
    config.set_escape_aliases(cfg, ["jk", "jj", "BAD1", "waytoolong", "x"])
    check("escape aliases keep only letter, 1-3 char",
          config.escape_aliases(cfg) == ["jk", "jj", "x"], config.escape_aliases(cfg))

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
