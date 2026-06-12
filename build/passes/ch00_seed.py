"""Foundation skills: word motion, dd, ci"."""

from build.common import C, S

SKILLS = [
    S("motion-word-forward", "Jump forward by word", "motion",
      "w moves the cursor to the start of the next word; a count multiplies it, "
      "so 2w jumps two words ahead. It is the bread-and-butter horizontal motion, "
      "far faster than hammering l.",
      ["w", "3w", "b", "e"], 1, [
        C(["deploy the staging build"], start_cursor=[1, 1], target=[1, 12],
          solution="2w", hint="a count in front of w repeats it",
          why="Two word-jumps land on 'staging' in two keystrokes."),
        C(["restart the failed worker"], start_cursor=[1, 1], target=[1, 13],
          solution="2w", hint="count then w",
          why="w counts words, not characters — distance is irrelevant."),
      ]),

    S("operator-delete-line", "Delete a whole line (dd)", "operator",
      "dd deletes the current line, linewise. Reach the target line with a motion "
      "first (j/k or a count), then dd. The deleted line goes to the unnamed "
      "register, ready to put back with p.",
      ["dd", "jdd", "2dd", "p"], 1, [
        C(["keep this record", "DELETE THIS LINE", "keep this one too"],
          ["keep this record", "keep this one too"],
          solution="jdd", hint="move down to the bad line, then delete it",
          why="j reaches the line, dd removes it linewise."),
        C(["alpha", "beta", "GONE", "gamma"], ["alpha", "beta", "gamma"],
          solution="jjdd", hint="two lines down, then dd",
          why="Stack motions before the operator to reach the target line."),
      ]),

    S("textobj-change-in-quotes", "Change inside quotes (ci\")", "text_object",
      "ci\" changes the text between the nearest pair of double quotes, wherever "
      "the cursor sits on the line — Vim searches forward to find them. The quotes "
      "stay; only their contents are replaced, and you land in insert mode.",
      ["ci\"", "ci'", "ci(", "cit"], 2, [
        C(['greeting = "hello"'], ['greeting = "howdy"'],
          solution='ci"howdy<Esc>', hint="change inside the quotes",
          why="ci\" finds the quoted text for you, then drops you in insert mode."),
        C(['path = "/tmp/old"'], ['path = "/var/new"'],
          solution='ci"/var/new<Esc>', hint="ci\" wipes the whole quoted string",
          why="One text-object swap replaces the entire path in a single motion."),
      ]),
]
