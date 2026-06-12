"""Render build/curriculum.py -> content/skills.json, verifying every challenge.

For each challenge that carries a `solution`, we replay it through real vim and
require that it (a) reaches the goal / target and (b) yields a definite keystroke
count, which becomes the authoritative `par_keys` (no hand-counting).  If any
challenge fails to verify, NOTHING is written and the script exits non-zero, so a
broken curriculum can never ship.

    python -m build.generate            # verify + write
    python -m build.generate --no-verify   # fast: skip the vim replay (par kept as-is)
    python -m build.generate --report      # verify, print per-skill detail, write
"""

from __future__ import annotations

import sys

from vimhjkl.challenge import Skill, is_cursor_category
from vimhjkl.grader import run_attempt, find_editor
from vimhjkl.keys import translate
from vimhjkl import store

from build import curriculum


GREEN, RED, YELLOW, GREY, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"


def _quit_for(category: str) -> str:
    return ":q\r" if is_cursor_category(category) else ":wq\r"


def verify_and_fill(skills_data: list[dict], *, verify: bool,
                    report: bool) -> tuple[list[Skill], list[str]]:
    errors: list[str] = []
    skills: list[Skill] = []
    seen_ids: set[str] = set()
    n_ch = n_verified = 0

    for sd in skills_data:
        skill = Skill.from_dict(sd)
        if skill.id in seen_ids:
            errors.append(f"duplicate skill id: {skill.id}")
        seen_ids.add(skill.id)
        for prob in skill.validate():
            errors.append(prob)

        for i, ch in enumerate(skill.challenges):
            n_ch += 1
            tag = f"{skill.id}[{i}]"
            if not ch.solution:
                errors.append(f"{tag}: no `solution` (required for verification)")
                continue
            if not verify:
                continue
            raw = translate(ch.solution) + _quit_for(skill.category)
            result = run_attempt(ch, skill.category, playback=raw)
            if result.aborted:
                errors.append(f"{tag}: vim aborted: {result.message}")
                continue
            if not result.correct:
                detail = (f"cursor={result.final_cursor} target={ch.target}"
                          if is_cursor_category(skill.category)
                          else f"got={result.final_buffer!r} want={ch.goal!r}")
                errors.append(f"{tag}: solution {ch.solution!r} did NOT verify "
                              f"({result.message} {detail})")
                continue
            # A buffer-graded challenge whose buffer is unchanged (goal == start)
            # can't be graded by buffer-diff — it's a yank challenge, graded on the
            # unnamed register.  Capture the register from this verifying replay so
            # authors never hand-write it, and reject a buffer that changes nothing
            # AND yanks nothing (a no-op bug — issue #5).
            if not is_cursor_category(skill.category) and ch.goal == ch.start:
                if not result.register:
                    errors.append(f"{tag}: solution {ch.solution!r} leaves the "
                                  f"buffer unchanged and yanks nothing (no-op)")
                    continue
                ch.yank = result.register
            # Authoritative par = the verified optimal-as-authored count.
            ch.par_keys = result.keystrokes
            n_verified += 1
            if report:
                print(f"  {GREEN}✓{RESET} {tag:<34} "
                      f"{ch.solution:<22} par={ch.par_keys}")
        skills.append(skill)

    summary = (f"{len(skills)} skills, {n_ch} challenges"
               + (f", {n_verified} verified" if verify else " (unverified)"))
    print(("\n" if report else "") + summary)
    return skills, errors


def merge_llm_pool(skills_data: list[dict]) -> int:
    """Fold verified-instance pool (content/llm_pool.json, written by
    build/llm_augment.py) into the matching skills by id, in place.

    The pool stores only authored fields (start/goal/solution/hint/why and the
    motion-only start_cursor/target); par_keys is intentionally absent so it is
    (re)computed authoritatively here, and every pooled instance still passes
    through the same real-vim gate as hand-authored ones.  Returns the number of
    instances merged.  Unknown skill ids are skipped (logged).
    """
    import json
    pool_path = store.CONTENT_DIR / "llm_pool.json"
    if not pool_path.exists():
        return 0
    pool = json.loads(pool_path.read_text(encoding="utf-8")).get("pool", {})
    by_id = {sd["id"]: sd for sd in skills_data}
    merged = 0
    for sid, instances in pool.items():
        sd = by_id.get(sid)
        if sd is None:
            print(f"{YELLOW}llm_pool: skipping unknown skill id {sid!r}{RESET}",
                  file=sys.stderr)
            continue
        existing = {tuple(c.get("start", [])) for c in sd["challenges"]}
        for inst in instances:
            if tuple(inst.get("start", [])) in existing:
                continue
            sd["challenges"].append(inst)
            existing.add(tuple(inst.get("start", [])))
            merged += 1
    if merged:
        print(f"{GREY}merged {merged} pooled instance(s) from llm_pool.json{RESET}")
    return merged


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    verify = "--no-verify" not in argv
    report = "--report" in argv

    if verify and find_editor() is None:
        print(f"{RED}no vim/nvim on PATH — re-run with --no-verify{RESET}",
              file=sys.stderr)
        return 2

    skills_data = curriculum.SKILLS
    if "--no-pool" not in argv:
        merge_llm_pool(skills_data)
    skills, errors = verify_and_fill(skills_data, verify=verify, report=report)

    if errors:
        print(f"\n{RED}{len(errors)} problem(s) — NOT writing skills.json:{RESET}",
              file=sys.stderr)
        for e in errors:
            print(f"  {RED}✗{RESET} {e}", file=sys.stderr)
        return 1

    store.save_skills(skills)
    if curriculum.TOTAL_LINES:
        # Local authoring cursor present — persist it (not distributed).
        state = {
            "source_file": curriculum.SOURCE_FILE,
            "last_line_read": curriculum.LAST_LINE_READ,
            "total_lines": curriculum.TOTAL_LINES,
            "topics_done": curriculum.TOPICS_DONE,
        }
        import json
        store.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        (store.CONTENT_DIR / "build_state.json").write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")

    print(f"{GREEN}wrote {store.SKILLS_PATH}{RESET}  "
          f"({len(skills)} skills, "
          f"{sum(len(s['challenges']) for s in skills)} challenges)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
