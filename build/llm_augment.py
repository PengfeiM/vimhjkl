"""Generate MORE practice instances for existing skills via an OpenAI-compatible LLM.

Why this is safe (and a reasonable idea):  every generated instance is replayed
through REAL vim before it is kept — the same gate ``build.generate`` uses.  A
start->solution->goal triple that does not actually reproduce in vim is dropped,
so the (untrusted) model only ever contributes verified material.  The model is
the *author*; vim is the *oracle*.

What the gate does NOT prove (so a human review pass is still required):
  * par_keys is computed from the model's own solution — a correct-but-clumsy
    solution verifies fine yet sets a wrong par.  We reject solutions that do not
    use one of the skill's key_commands (kills the obvious off-skill cases) and
    print every accepted instance compactly so optimality can be eyeballed.
  * teach/hint/why prose and copyright echoes are not machine-checkable.

It does NOT invent new skills — it deepens the existing curriculum with extra
instances, because a skill's grading style + optimal path is what we can verify.

PIPELINE
  1. Load content/skills.json (the built curriculum).
  2. For each selected skill, one focused API call (full context: grading rules,
     teach text, key_commands, sample instances, the keystroke vocabulary, the
     copyright rule) asks for N fresh instances.  Calls run in parallel.
  3. Verify each candidate through real vim; drop failures and off-skill / dup
     starts.
  4. Append survivors to content/llm_pool.json (append + dedup on `start`), which
     `build.generate` folds back into the matching skill and re-verifies.

USAGE
    export OPENAI_API_KEY=sk-...
    # FILL THE GAPS (recommended): top every skill up to --target instances in
    # one command — picks the under-target skills and sizes each request itself:
    uv run python -m build.llm_augment --fill            # target 6/skill
    uv run python -m build.llm_augment --fill --target 8 --model gpt-4o
    # OpenAI (default), uniform N per skill:
    uv run python -m build.llm_augment --per-skill 6 --workers 10
    # DeepSeek / any OpenAI-compatible endpoint:
    OPENAI_BASE_URL=https://api.deepseek.com/v1 OPENAI_MODEL=deepseek-chat \
        uv run python -m build.llm_augment
    # one skill only, see candidates without writing the pool:
    uv run python -m build.llm_augment --skill textobj-change-inner-word --dry-run

    # then review + bake in:
    uv run python -m build.generate --report

FLAGS
    --per-skill N   instances to request per skill (default 6)
    --workers N     parallel API calls (default 10)
    --skill ID      restrict to one or more skill ids (repeatable)
    --category CAT  restrict to one category (operator, motion, text_object, ...)
    --model NAME    override $OPENAI_MODEL (default gpt-4o-mini)
    --base-url URL  override $OPENAI_BASE_URL (default https://api.openai.com/v1)
    --dry-run       generate + verify + report, but do NOT write the pool
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from vimhjkl.challenge import Challenge, is_cursor_category, wants_command, CATEGORIES
from vimhjkl.grader import run_attempt, find_editor
from vimhjkl.keys import translate
from vimhjkl import store

GREEN, RED, YELLOW, GREY, CYAN, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[36m", "\033[0m")

POOL_PATH = store.CONTENT_DIR / "llm_pool.json"
REJECTS_PATH = store.CONTENT_DIR / "llm_rejects.json"
PROJECT_ROOT = store.PROJECT_ROOT


def load_dotenv() -> None:
    """Load KEY=VALUE pairs from a .env (project root or cwd) into os.environ,
    without overriding values already set in the real environment.  Stdlib only —
    no python-dotenv dependency."""
    for path in (PROJECT_ROOT / ".env", os.path.join(os.getcwd(), ".env")):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)
        return  # first .env found wins

# Authored fields we persist; par_keys is deliberately omitted so build.generate
# recomputes it from real vim (mirrors how the hand-authored passes omit it).
_BUFFER_FIELDS = ("start", "goal", "solution", "hint", "why", "start_cursor")
_CURSOR_FIELDS = ("start", "solution", "hint", "why", "start_cursor", "target")


# --------------------------------------------------------------------------- #
# Prompt construction
# --------------------------------------------------------------------------- #

_KEY_VOCAB = (
    "Write `solution` as the literal keys a vim user types, using these tokens "
    "for special keys: <Esc> <CR> <Tab> <BS> <Space> <C-r> <C-n> <C-x> <C-a> "
    "(any <C-x> control chord), <Up> <Down> <Left> <Right>, and <lt> for a "
    "literal '<'. Everything else is the raw character. Examples of well-formed "
    "solutions: \"ciwhello<Esc>\", \"f,d/END<CR>\", \":%s/old/new/g<CR>\", "
    "\"qadd@a<Esc>\". The solution must START in normal mode and END back in "
    "normal mode (include the <Esc> that leaves insert mode); do NOT include a "
    "trailing :w / :wq / :q — the harness adds the save/quit itself."
)


def _sample_instances(challenges: list[dict], cursor: bool, k: int = 3) -> str:
    out = []
    for c in challenges[:k]:
        item = {"start": c.get("start", []), "solution": c.get("solution", "")}
        if cursor:
            item["start_cursor"] = c.get("start_cursor")
            item["target"] = c.get("target")
        else:
            item["goal"] = c.get("goal", [])
        item["hint"] = c.get("hint", "")
        item["why"] = c.get("why", "")
        out.append(item)
    return json.dumps(out, ensure_ascii=False, indent=2)


def build_prompt(skill: dict, n: int) -> tuple[str, str]:
    cursor = is_cursor_category(skill["category"])
    spec = CATEGORIES[skill["category"]]

    if cursor:
        shape = (
            "This is a MOTION skill: the buffer is NOT changed. Each instance has "
            "`start` (buffer lines), `start_cursor` ([line, col], 1-based, where the "
            "cursor begins), `target` ([line, col], 1-based, where the motion must "
            "land), `solution`, `hint`, `why`. Do NOT include `goal`."
        )
        fields = "start (list of strings), start_cursor ([line,col]), target ([line,col]), solution, hint, why"
    else:
        shape = (
            "Each instance transforms the buffer: it has `start` (buffer lines BEFORE) "
            "and `goal` (buffer lines AFTER), plus `solution`, `hint`, `why`. Optionally "
            "`start_cursor` ([line,col], 1-based) if the cursor must begin somewhere "
            "specific. The `goal` must be EXACTLY what the buffer becomes after running "
            "`solution` from `start`."
        )
        fields = "start (list of strings), goal (list of strings), solution, hint, why, optional start_cursor ([line,col])"
        if wants_command(skill["category"]):
            shape += (" The idiomatic path is a SINGLE ex command (e.g. :g, :s, "
                      ":normal, with ranges).")

    # Range/scope drills are only meaningful when the scope is load-bearing.  Warn
    # the model (and mirror the build-time motivation gate) so it stops emitting
    # one-occurrence buffers where a whole-file :%… would do the same thing.
    scope_rule = ""
    if not cursor and wants_command(skill["category"]):
        scope_rule = (
            "\n- SCOPE MUST BITE — if your solution uses a line range or marks "
            "('a,'b, :2,5, visual range), the target MUST also appear OUTSIDE that "
            "range so a whole-file :%… would change the WRONG lines. An instance "
            "where :%<cmd> reaches the same goal as the ranged version is REJECTED "
            "automatically — the range has to be the reason it's correct.")

    system = (
        "You are a witty vim instructor with a great sense of humor, writing "
        "practice drills for a terminal trainer. Your example text is vivid, funny, "
        "and memorable — never filler. You output ONLY a JSON object and nothing else."
    )
    user = f"""\
Author {n} NEW practice instances for ONE vim skill. They will be verified by
replaying `solution` through real vim, so each one MUST be mechanically correct.

SKILL: {skill['title']}  (id: {skill['id']})
CATEGORY: {skill['category']} — {spec.blurb}
TECHNIQUE TAUGHT: {skill['teach']}
KEY COMMANDS to practise: {', '.join(skill['key_commands'])}

{shape}

KEYSTROKE FORMAT. {_KEY_VOCAB}

VOICE — this is the part people actually read, so make it good:
- The example buffers and hints should be CREATIVE, FUNNY, and CONCRETE. Tiny
  jokes, absurd scenarios, vivid nouns, real-feeling code with cheeky names,
  weird shopping lists, dramatic log lines, petty TODOs. Make the learner smirk.
- BANNED — never use these tired placeholders: "foo/bar/baz", "Alice"/"Bob",
  "Hello World", "this is a test"/"this is an example", "lorem ipsum",
  "item1/item2/item3", "apple orange banana", generic "x/y/z" or "line one/two".
  If you're about to write filler, write something with personality instead.
- Hints should be short and have a bit of attitude, but still tell the truth
  about what to do. Same for `why`: punchy, not a textbook sentence.
- Specifics beat abstractions: not "a list of words" but "gremlin goblin wizard
  troll"; not "function foo()" but "function summonDragon()".

HARD RULES (these still win over voice — a funny drill that doesn't verify is useless):
- Every `solution` MUST exercise this skill: it must use one of the key commands
  above ({', '.join(skill['key_commands'])}). Do not solve it a different way.
- Make `solution` the OPTIMAL (fewest-keystroke) idiomatic way to do the edit —
  par is computed from it, so a clumsy solution mis-scores learners.
- MOTIVATION — the buffer must NEED this technique. Size and shape each example so
  this skill is the SHORTEST correct path: if a learner could reach the goal faster
  another way, the drill is broken and worthless. Give the move enough to chew on —
  enough lines, matches, or repetition that doing it by hand would be tedious (a
  global/macro/sort/count/dot skill on a 1-line buffer is pointless).{scope_rule}
- `start`, `solution`, and `goal`/`target` must be perfectly consistent: run the
  keys in your head and make `goal` EXACTLY what the buffer becomes. The humor
  lives in the words, not in fudging the edit.
- COPYRIGHT: invent your OWN text. Do NOT reuse any copyrighted book/song/source
  text. Keep buffers small (1-6 lines).
- Vary the theme, difficulty, and context across all {n} instances — no two should
  feel like reskins of each other. Do not duplicate the existing ones below.

EXISTING INSTANCES — copy their JSON SHAPE only; your example text should be far
more colorful than these (and must not duplicate them):
{_sample_instances(skill.get('challenges', []), cursor)}

Respond with ONLY this JSON object (no markdown fences, no commentary):
{{"instances": [ {{ {fields} }}, ... ]}}"""
    return system, user


# --------------------------------------------------------------------------- #
# OpenAI-compatible chat call (stdlib only)
# --------------------------------------------------------------------------- #

def chat(system: str, user: str, *, base_url: str, model: str, api_key: str,
         timeout: float = 120.0) -> str:
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.95,
    }).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["choices"][0]["message"]["content"]


def parse_instances(text: str) -> list[dict]:
    """Tolerant JSON extraction: strip code fences, grab the outermost object."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if t.count("```") >= 2 else t.strip("`")
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in response")
    obj = json.loads(t[start:end + 1])
    inst = obj.get("instances", obj if isinstance(obj, list) else [])
    if not isinstance(inst, list):
        raise ValueError("`instances` is not a list")
    return inst


# --------------------------------------------------------------------------- #
# Verification (same gate as build.generate)
# --------------------------------------------------------------------------- #

# Chars that make up an ex address/range between the ':' and the command verb
# (line numbers, ., $, %, marks 'a, visual range '<,'>, +/- offsets, commas).
_RANGE = r"[%0-9.$,'<>+ \-]*"


def uses_skill(solution: str, key_commands: list[str]) -> bool:
    """Best-effort off-skill signal: does `solution` exercise a taught command?

    key_commands are authored as illustrations, often templated (':%s///g',
    ':g//d') or representative ('\\v<x>'), so they are NOT literal substrings of a
    real solution.  Two matchers:
      * ex commands (start with ':'): match on the command VERB (the letters
        right after the colon + optional range).  So ':%s///g' (verb 's') matches
        ':%s/a/b/g', ':g//d' (verb 'g') matches ':g/^#/d', ':t' matches ':1t$'.
      * everything else: plain substring (ciw, %, daw...).
    A miss is a soft signal only (the caller warns, never drops) — vim already
    proved correctness, and key_commands are too loose to reject on."""
    for kc in key_commands:
        if not kc:
            continue
        if kc.startswith(":"):
            m = re.match(r":" + _RANGE + r"([A-Za-z]+)", kc)
            verb = m.group(1) if m else None
            if verb and re.search(r":" + _RANGE + re.escape(verb), solution):
                return True
        elif kc in solution:
            return True
    return False


# High-precision filler patterns — these are almost never legitimate creative
# text, so we HARD-reject them (word-boundary, so "barbarian"/"foobar-free"
# survive).  The prompt also forbids them; this is the safety net.
_CLICHE_RE = re.compile(
    # tokens that are essentially never legitimate creative text
    r"\b(foo|baz|qux|quux|alice|bob)\b"
    # 'bar' only as part of the foo-family cluster ('the bar was loud' is fine)
    r"|\bfoo[ -]?bar\b"
    r"|hello,? world|lorem ipsum|this is (a test|an example)"
    # item1/item2 placeholders (digit, no space) — but NOT 'item 7'
    r"|\bitem\d\b|apple,? orange,? banana|\bline (one|two)\b",
    re.IGNORECASE,
)


def cliche_hit(inst: dict) -> str:
    """Return the first banned-filler phrase found in the buffer/hint, else ''."""
    text = " ".join(inst.get("start", []) + [inst.get("hint", "")])
    m = _CLICHE_RE.search(text)
    return m.group(0) if m else ""


def normalize_instance(inst: dict) -> dict:
    """Coerce common model-output quirks into the exact shape we verify, so good
    data is not falsely rejected on formatting alone.

      * a buffer given as a bare string -> [string] (NOT list("string"));
      * a buffer with newlines in one string -> split into lines;
      * non-string buffer cells -> str();
      * [row, col] cursor/target -> [int, int] when numeric-ish.
    Returns a NEW dict; never raises (bad shapes fall through to verification)."""
    def as_lines(v):
        if v is None:
            return []
        if isinstance(v, str):
            return v.split("\n")
        if isinstance(v, list):
            out = []
            for cell in v:
                if isinstance(cell, str):
                    out.extend(cell.split("\n"))
                else:
                    out.append(str(cell))
            return out
        return v  # leave anything weird for the verifier to reject honestly

    def as_pos(v):
        if isinstance(v, list) and len(v) == 2:
            try:
                return [int(v[0]), int(v[1])]
            except (TypeError, ValueError):
                return v
        return v

    out = dict(inst)
    if "start" in out:
        out["start"] = as_lines(out["start"])
    if "goal" in out:
        out["goal"] = as_lines(out["goal"])
    if out.get("start_cursor") is not None:
        out["start_cursor"] = as_pos(out["start_cursor"])
    if out.get("target") is not None:
        out["target"] = as_pos(out["target"])
    return out


def _to_challenge(inst: dict, cursor: bool) -> Challenge:
    return Challenge(
        start=list(inst.get("start", [])),
        goal=list(inst.get("goal", [])),
        start_cursor=inst.get("start_cursor"),
        target=inst.get("target"),
        solution=inst.get("solution", ""),
        hint=inst.get("hint", ""),
        why=inst.get("why", ""),
    )


# --------------------------------------------------------------------------- #
# Motivation gate: is the taught SCOPE actually necessary?
# --------------------------------------------------------------------------- #
#
# A range/marks drill is pointless if the buffer is so small that the SAME ex
# command run over the WHOLE file reaches the same goal — that's the "change
# 'thy' on the one line that has it with :'a,'b s///" failure.  We derive the
# naive shortcut from the instance's OWN solution (no general solver): take each
# ':...<CR>' command, and if it carries an explicit multi-line range (marks
# 'a,'b or line numbers N,M — anything narrower than %), rewrite that range to
# '%' and replay.  If the whole-file version also lands on the goal, the scope
# added nothing, so we reject the instance as unmotivated.

# An ex address atom (line number, ., $, %, a mark 'a / '< / '>, or a +/- offset)
# and a leading range built from atoms joined by ',' or ';'.  Mark atoms carry a
# letter, so a plain "[range chars]" class can't capture them — this can.
_ADDR = r"(?:\d+|\.|\$|%|'[A-Za-z<>]|[+\-]\d*)"
_LEAD_RANGE = re.compile(r"^(" + _ADDR + r"(?:\s*[,;]\s*" + _ADDR + r")*)(.+)$")


def _broaden_range(excmd: str) -> str | None:
    """Rewrite an ex command's explicit multi-line range to '%' (whole file).

    Returns the broadened command (without leading ':'), or None when there is
    no explicit multi-line range narrower than the whole file to broaden (already
    '%', a bare current-line command, or a :g/:v that is whole-file by nature)."""
    m = _LEAD_RANGE.match(excmd)
    if not m:
        return None
    rng, rest = m.group(1), m.group(2)
    # Only meaningful when the range spans multiple lines (a ',' or ';' range)
    # and isn't already the whole file.
    if "," not in rng and ";" not in rng:
        return None
    if rng.replace(" ", "") in ("%", "1,$"):
        return None
    return "%" + rest


def scope_unmotivated(inst: dict, skill: dict) -> bool:
    """True if a whole-file version of the solution's ranged command also reaches
    the goal — i.e. the range/marks scope was unnecessary on this buffer."""
    if is_cursor_category(skill["category"]):
        return False
    sol = inst.get("solution", "")
    for excmd in re.findall(r":(.+?)<CR>", sol):
        broad = _broaden_range(excmd)
        if broad is None:
            continue
        ch = _to_challenge(inst, cursor=False)
        try:
            res = run_attempt(ch, skill["category"],
                              playback=translate(":" + broad + "<CR>") + ":wq\r")
        except Exception:  # noqa: BLE001 — a probe failure never blocks the run
            continue
        if not res.aborted and res.correct:
            return True
    return False


def verify_instance(inst: dict, skill: dict) -> tuple[bool, str, int, str]:
    """Return (ok, reason, par, warn).

    `ok` means the instance is present and actually reproduces in real vim — the
    hard, trustworthy gate.  `warn` is a soft note (e.g. the solution does not
    obviously use a taught command) for the mandatory human review; it never
    drops a verified instance."""
    cursor = is_cursor_category(skill["category"])
    sol = inst.get("solution", "")
    if not sol:
        return False, "no solution", 0, ""
    if not list(inst.get("start", [])):
        return False, "no start buffer", 0, ""
    if not cursor and not list(inst.get("goal", [])):
        return False, "no goal buffer", 0, ""
    if cursor and not inst.get("target"):
        return False, "no target cursor", 0, ""
    hit = cliche_hit(inst)
    if hit:
        return False, f"cliché filler text ({hit!r})", 0, ""

    ch = _to_challenge(inst, cursor)
    quit_seq = ":q\r" if cursor else ":wq\r"
    try:
        res = run_attempt(ch, skill["category"], playback=translate(sol) + quit_seq)
    except Exception as e:  # noqa: BLE001 — verification must never crash the run
        return False, f"vim error: {e}", 0, ""
    if res.aborted:
        return False, f"vim aborted: {res.message}", 0, ""
    if not res.correct:
        return False, f"did not reach goal ({res.message})", 0, ""
    if scope_unmotivated(inst, skill):
        return False, "scope unnecessary (whole-file :%… reaches the same goal)", 0, ""

    warn = "" if uses_skill(sol, skill["key_commands"]) else "off-skill?"
    return True, "ok", res.keystrokes, warn


def _reason_bucket(why: str) -> str:
    """Collapse a per-instance reason into a coarse bucket for the histogram."""
    if why.startswith("did not reach goal"):
        return "solution didn't reproduce the goal/target in vim"
    if why.startswith("duplicate"):
        return "duplicate start buffer"
    if why.startswith("cliché"):
        return "cliché filler text (foo/bar, Alice/Bob, ...)"
    if why.startswith("vim aborted") or why.startswith("vim error"):
        return "vim aborted / error"
    if why.startswith("no "):
        return "missing required field (start/goal/target/solution)"
    return why


def _slim(inst: dict, cursor: bool) -> dict:
    fields = _CURSOR_FIELDS if cursor else _BUFFER_FIELDS
    return {k: inst[k] for k in fields if inst.get(k) not in (None, [], "")}


# --------------------------------------------------------------------------- #
# Per-skill worker
# --------------------------------------------------------------------------- #

def process_skill(skill: dict, n: int, cfg) -> dict:
    """Generate + verify for one skill. Returns a result record (never raises)."""
    rec = {"id": skill["id"], "kept": [], "rejected": [], "error": None}
    cursor = is_cursor_category(skill["category"])
    existing_starts = {tuple(c.get("start", [])) for c in skill.get("challenges", [])}
    try:
        system, user = build_prompt(skill, n)
        raw = chat(system, user, base_url=cfg.base_url, model=cfg.model,
                   api_key=cfg.api_key)
        candidates = parse_instances(raw)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        rec["error"] = f"API call failed: {e}"
        return rec
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"bad response: {e}"
        return rec

    seen = set(existing_starts)
    for raw_inst in candidates:
        if not isinstance(raw_inst, dict):
            continue
        inst = normalize_instance(raw_inst)
        key = tuple(inst.get("start", []))
        if key in seen:
            rec["rejected"].append((inst, "duplicate start"))
            continue
        ok, reason, par, warn = verify_instance(inst, skill)
        if ok:
            seen.add(key)
            rec["kept"].append((_slim(inst, cursor), par, warn))
        else:
            rec["rejected"].append((inst, reason))
    return rec


# --------------------------------------------------------------------------- #
# Pool IO
# --------------------------------------------------------------------------- #

def load_pool() -> dict:
    if POOL_PATH.exists():
        return json.loads(POOL_PATH.read_text(encoding="utf-8")).get("pool", {})
    return {}


def save_pool(pool: dict) -> None:
    POOL_PATH.write_text(
        json.dumps({"version": 1, "pool": pool}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="LLM-augment vimhjkl practice instances.")
    p.add_argument("--per-skill", type=int, default=6)
    p.add_argument("--workers", type=int, default=10)
    p.add_argument("--skill", action="append", default=[], dest="skills")
    p.add_argument("--category", default=None)
    # No OPENAI_API_KEY but a DEEPSEEK_API_KEY ⇒ default to DeepSeek's
    # OpenAI-compatible endpoint and model (overridable as usual).
    _deepseek = (not os.environ.get("OPENAI_API_KEY")
                 and bool(os.environ.get("DEEPSEEK_API_KEY")))
    p.add_argument("--model", default=os.environ.get(
        "OPENAI_MODEL", "deepseek-chat" if _deepseek else "gpt-4o-mini"))
    p.add_argument("--base-url", default=os.environ.get(
        "OPENAI_BASE_URL",
        "https://api.deepseek.com" if _deepseek else "https://api.openai.com/v1"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--fill", action="store_true",
                   help="auto-target every skill below --target instances and "
                        "request enough to fill each gap (one command, no manual "
                        "skill/category picking)")
    p.add_argument("--target", type=int, default=6,
                   help="--fill goal: instances per skill (default 6)")
    args = p.parse_args(argv)

    args.api_key = (os.environ.get("OPENAI_API_KEY", "")
                    or os.environ.get("DEEPSEEK_API_KEY", ""))
    if not args.api_key:
        print(f"{RED}set OPENAI_API_KEY or DEEPSEEK_API_KEY (and optionally "
              f"OPENAI_BASE_URL / OPENAI_MODEL){RESET}", file=sys.stderr)
        return 2
    if find_editor() is None:
        print(f"{RED}no vim/nvim on PATH — verification impossible{RESET}",
              file=sys.stderr)
        return 2

    skills = [s.to_dict() for s in store.load_skills()]
    if args.skills:
        skills = [s for s in skills if s["id"] in set(args.skills)]
    if args.category:
        skills = [s for s in skills if s["category"] == args.category]
    if not skills:
        print(f"{RED}no skills matched the filter{RESET}", file=sys.stderr)
        return 1

    pool_data = load_pool()

    # How many instances to request per skill.  In --fill mode this is sized to
    # each skill's gap below --target (counting already-pooled instances), and
    # over-asked to absorb the verification reject rate; otherwise it is uniform.
    if args.fill:
        req: dict[str, int] = {}
        for s in skills:
            # Count UNIQUE starts across the built challenges and the pool.  The
            # build already merges the pool into skills.json, so adding the two
            # lengths double-counts; a union of `start` keys is correct whether or
            # not `generate` has been re-run since the pool last changed.
            starts = {tuple(c.get("start", [])) for c in s["challenges"]}
            starts |= {tuple(c.get("start", [])) for c in pool_data.get(s["id"], [])}
            have = len(starts)
            gap = args.target - have
            if gap > 0:
                # over-ask ~2.5x (≈40% pass rate), clamp to a sane prompt size
                req[s["id"]] = max(4, min(15, -(-gap * 5 // 2)))
        skills = [s for s in skills if s["id"] in req]
        if not skills:
            print(f"{GREEN}every skill is already at/above {args.target} "
                  f"instances — nothing to fill.{RESET}")
            return 0
        ask = lambda sid: req[sid]
        print(f"{CYAN}filling gaps to {args.target}/skill · {len(skills)} skill(s) "
              f"below target · {args.workers} workers · model={args.model}{RESET}\n",
              flush=True)
    else:
        ask = lambda sid: args.per_skill
        print(f"{CYAN}augmenting {len(skills)} skill(s) · {args.per_skill}/skill · "
              f"{args.workers} workers · model={args.model}{RESET}\n", flush=True)

    total_kept = total_rej = 0
    reasons: Counter = Counter()
    rejects: dict = {}
    n = len(skills)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(process_skill, s, ask(s["id"]), args): s["id"]
                for s in skills}
        for done, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            tag = f"{GREY}[{done}/{n}]{RESET}"
            if rec["error"]:
                print(f"{tag} {RED}✗ {rec['id']}: {rec['error']}{RESET}", flush=True)
                reasons["API/response error"] += 1
                continue
            kept, rej = rec["kept"], rec["rejected"]
            total_kept += len(kept)
            total_rej += len(rej)
            head = (GREEN if kept else GREY)
            print(f"{tag} {head}{rec['id']}{RESET}  +{len(kept)} kept, "
                  f"{len(rej)} rejected", flush=True)
            for inst, par, warn in kept:
                sol = inst.get("solution", "")
                start = " / ".join(inst.get("start", []))[:60]
                tail = (f"-> {inst.get('target')}" if "target" in inst
                        else "-> " + " / ".join(inst.get("goal", []))[:40])
                flag = f" {YELLOW}⚠ {warn}{RESET}" if warn else ""
                print(f"    {GREEN}✓{RESET} {sol:<24} par={par:<3} "
                      f"{GREY}[{start}] {tail}{RESET}{flag}", flush=True)
            for inst, why in rej:
                reasons[_reason_bucket(why)] += 1
                sol = inst.get("solution", "") if isinstance(inst, dict) else str(inst)
                print(f"    {YELLOW}·{RESET} {sol[:24]:<24} {GREY}{why}{RESET}",
                      flush=True)
                if isinstance(inst, dict):
                    rejects.setdefault(rec["id"], []).append({**inst, "_reason": why})
            if kept and not args.dry_run:
                bucket = pool_data.setdefault(rec["id"], [])
                have = {tuple(c.get("start", [])) for c in bucket}
                for inst, _par, _warn in kept:
                    if tuple(inst.get("start", [])) not in have:
                        bucket.append(inst)
                        have.add(tuple(inst.get("start", [])))

    print(f"\n{CYAN}{total_kept} verified instance(s) kept, {total_rej} "
          f"rejected.{RESET}")
    if reasons:
        print(f"{GREY}why rejected:{RESET}")
        for why, cnt in reasons.most_common():
            print(f"    {cnt:>4}  {why}")
    if rejects:
        REJECTS_PATH.write_text(
            json.dumps({"version": 1, "rejects": rejects}, indent=2,
                       ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{GREY}rejected instances saved for inspection → {REJECTS_PATH}\n"
              f"    (each carries a \"_reason\"; rescue good ones into llm_pool.json "
              f"and re-run build.generate){RESET}")
    if args.dry_run:
        print(f"{YELLOW}--dry-run: pool NOT written.{RESET}")
    elif total_kept:
        save_pool(pool_data)
        print(f"{GREEN}wrote {POOL_PATH}{RESET}  "
              f"→ review, then: {CYAN}uv run python -m build.generate --report{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
