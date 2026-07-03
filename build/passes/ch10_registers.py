"""Registers: delete, yank, put.

System clipboard ("+/"*) and the black-hole register ("_) are environment- or
side-effect-based (no buffer change to grade), so they're noted, not drilled.
"""

from build.common import C, S

SKILLS = [
    S("register-transpose", "Transpose with delete + put (xp, ddp)", "register",
      "Vim calls cut/copy/paste delete/yank/put. p puts the unnamed register "
      "AFTER the cursor (P before). Two famous one-liners fall out of this: xp "
      "swaps two characters, and ddp swaps two lines — delete into the register, "
      "then put it back on the other side.",
      ["p", "P", "xp", "ddp"], 2, [
        C(["hte cat"], ["the cat"],
          solution="xp",
          hint="delete the char, put it back after the next one",
          why="xp transposes the two leading characters in one breath."),
        C(["return result", "compute result"], ["compute result", "return result"],
          solution="ddp",
          hint="delete the line, put it back below",
          why="ddp swaps a line with the one beneath it — fix the wrong order fast."),
      ]),

    S("register-yank-reliable", "Yank survives a delete (\"0)", "register",
      "Every delete (x, d, c — and a visual paste, which deletes what it "
      "replaces) overwrites the unnamed register, so a yank you meant to paste "
      "twice gets clobbered after the first paste. The yank register \"0 is set "
      "ONLY by y, so it survives all of that: yank once, then paste reliably "
      "with \"0p as many times as you need.",
      ["\"0p", "yiw", "viw\"0p", "<C-r>0"], 4, [
        # TWO placeholders: the first visual paste works from unnamed, but it
        # swaps the replaced SPARE back INTO unnamed — the second paste is where
        # "0 earns its keys (re-yanking the pasted word costs more).
        C(["primary = main", "standby = SPARE", "mirror = SPARE"],
          ["primary = main", "standby = main", "mirror = main"],
          start_cursor=[1, 11],
          solution='yiwjviwpjviw"0p',
          hint="yank the value once; after the first paste unnamed holds "
               "SPARE — \"0 still has your yank for the second",
          why="\"0 is written only by y, so it survives the visual paste's "
              "implicit delete and pastes 'main' again untouched.",
          why_not="viwp twice pastes 'main' then 'SPARE' — the first paste "
                  "traded your yank for the word it replaced; re-yanking "
                  "each time costs more keys than \"0."),
        C(["primary = wss://relay.internal:8443",
           "# point every consumer at the tested relay",
           "consumer_a = TBD", "consumer_b = TBD", "consumer_c = TBD"],
          ["primary = wss://relay.internal:8443",
           "# point every consumer at the tested relay",
           "consumer_a = wss://relay.internal:8443",
           "consumer_b = wss://relay.internal:8443",
           "consumer_c = wss://relay.internal:8443"],
          start_cursor=[1, 11],
          solution='yiW/TBD<CR>viWpnviW"0pnviW"0p',
          hint="one yank of the URL feeds all three slots — \"0 outlives "
               "every visual paste along the way",
          why="Each viWp shoves the replaced TBD into unnamed, but \"0 keeps "
              "the URL for slots two and three.",
          why_not="Retyping that URL three times is the slow-motion version; "
                  "plain viWp dies after slot one because unnamed now holds "
                  "TBD."),
      ]),

    S("register-named", "Stash text in a named register (\"a)", "register",
      "The 26 named registers \"a-\"z each hold their own text: \"ay{motion} yanks "
      "into a, \"ap puts from it. A lowercase letter overwrites; the uppercase "
      "\"A APPENDS to the same register. Use them to carry several snippets at once "
      "without them stepping on each other — the unnamed register is wiped by "
      "every delete and every visual paste, but \"a and \"b never go stale.",
      ["\"ayiW", "\"byiW", "\"ap", "viW\"bp"], 4, [
        # Two different labels, four slots, alternating.  The unnamed register
        # CANNOT carry this: the first visual paste dumps the replaced TODO into
        # it, so every later slot needs a re-yank + an extra travel pass.  Two
        # named registers are filled once and never go stale.
        C(["crit = ALERT-PAGE-ONCALL", "warn = TICKET-NEXT-SPRINT", "",
           "[db timeouts]", "severity: TODO",
           "[disk almost full]", "severity: TODO",
           "[api 5xx spike]", "severity: TODO",
           "[css off by one px]", "severity: TODO"],
          ["crit = ALERT-PAGE-ONCALL", "warn = TICKET-NEXT-SPRINT", "",
           "[db timeouts]", "severity: ALERT-PAGE-ONCALL",
           "[disk almost full]", "severity: TICKET-NEXT-SPRINT",
           "[api 5xx spike]", "severity: ALERT-PAGE-ONCALL",
           "[css off by one px]", "severity: TICKET-NEXT-SPRINT"],
          solution='$"ayiWj$"byiW/TODO<CR>viW"apnviW"bpnviW"apnviW"bp',
          hint="yank each label into its own register, then fill the slots "
               "in one pass — viW\"ap pastes over the placeholder",
          why="Both labels ride along at once: \"a and \"b survive every "
              "visual paste, so you fill all four slots in a single sweep.",
          why_not="yiW + viWp works exactly once — that first paste shoves "
                  "the replaced TODO into the unnamed register, and your "
                  "label is gone; two labels means two full passes."),
        C(["on  = enabled=true,audit=true", "off = enabled=false,audit=false", "",
           "flag_checkout: PENDING", "flag_search: PENDING",
           "flag_uploads: PENDING", "flag_export: PENDING"],
          ["on  = enabled=true,audit=true", "off = enabled=false,audit=false", "",
           "flag_checkout: enabled=true,audit=true",
           "flag_search: enabled=false,audit=false",
           "flag_uploads: enabled=true,audit=true",
           "flag_export: enabled=false,audit=false"],
          solution='$"ayiWj$"byiW/PENDING<CR>viW"apnviW"bpnviW"apnviW"bp',
          hint="stash the on-value in \"a and the off-value in \"b, then "
               "alternate them over the PENDING slots",
          why="One trip down the file settles all four flags — each register "
              "keeps its value no matter how many times you paste.",
          why_not="With only the unnamed register the first viWp poisons it "
                  "with PENDING; you'd re-yank at every other slot or walk "
                  "the file twice."),
      ]),
]
