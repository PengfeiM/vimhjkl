"""Precision text objects, % matching, search-as-operand."""

from build.common import C, S

SKILLS = [
    S("textobj-change-inner-word", "Change the word under the cursor (ciw)",
      "text_object",
      "iw is the inner-word text object: ciw changes the WHOLE word the cursor is "
      "on — from any position within it — without first moving to its start. It is "
      "the everyday way to swap one word for another, and it is dot-repeatable.",
      ["ciw", "caw", "diw", "viw"], 2,
      [
        C(["color = crimson"], ["color = teal"],
          start_cursor=[1, 9], solution="ciwteal<Esc>",
          hint="the cursor sits on the value — change just it",
          why="ciw replaces the whole word from anywhere inside it."),
        C(["tmp = computeTotal()"], ["result = computeTotal()"],
          start_cursor=[1, 1], solution="ciwresult<Esc>",
          hint="rename the variable without selecting it first",
          why="ciw swaps the identifier under the cursor in one move."),
      ]),

    S("textobj-change-inside-delims", "Change inside delimiters (ci( ci{ cit ...)",
      "text_object",
      "Text objects act on structure, not position. i{delim} targets the text "
      "INSIDE a pair of (), {}, [], <>, quotes, or <xml>tags</xml> — from anywhere "
      "within them. ci( changes inside parens, ci{ inside braces, cit inside a "
      "tag. Two keystrokes select what would take many motions.",
      ["ci(", "ci{", "ci[", "cit"], 2, [
        C(["call(oldarg)"], ["call(newarg)"],
          solution="ci(newarg<Esc>",
          hint="change inside the parentheses",
          why="ci( grabs the argument list wherever the cursor sits."),
        C(["config = {debug}"], ["config = {ok}"],
          solution="ci{ok<Esc>",
          hint="change inside the braces",
          why="ci{ targets the block's contents, braces left intact."),
        C(["<p>old text</p>"], ["<p>fresh</p>"],
          solution="citfresh<Esc>",
          hint="change inside the tag",
          why="cit reads the XML structure — no counting characters."),
        C(["arr[OLD]"], ["arr[NEW]"],
          solution="ci[NEW<Esc>",
          hint="change inside the square brackets",
          why="ci[ swaps the subscript in one move."),
        # Multiline: i{ spans lines, so one ci{ guts a whole block body —
        # the everyday "rewrite this function's stub" move in real code.
        C(["registry.routes({", "    home: '/',", "    about: '/about',", "})"],
          ["registry.routes({", "    health: '/healthz',", "})"],
          start_cursor=[2, 5],
          solution="ci{health: '/healthz',<Esc>",
          hint="ci{ works across lines — the whole block body is one object",
          why="Text objects read structure, so a multiline { } body falls to "
              "the same two keys as a one-liner."),
      ]),

    S("textobj-around-vs-inside", "Around vs inside (daw, das, dap, di()",
      "text_object",
      "Bounded text objects come in two flavours: i{obj} is INSIDE (just the "
      "word/sentence/paragraph), a{obj} is AROUND (and grabs a trailing space or "
      "blank line too). Rule of thumb: delete with the 'a' form (daw, das) for "
      "clean spacing; change with the 'i' form (ciw) so you don't run words "
      "together.",
      ["daw", "das", "dap", "diw"], 3, [
        C(["the quick temporary hack works"], ["the quick hack works"],
          start_cursor=[1, 11], solution="daw",
          hint="delete A word — it takes the trailing space too",
          why="daw leaves no double space; diw would."),
        C(["First sentence. Drop me here. Third one."],
          ["First sentence. Third one."],
          solution="fDdas",
          hint="land in the middle sentence, delete A sentence",
          why="das removes the whole sentence and its trailing space."),
        C(["total = sum(a, b, c)"], ["total = sum()"],
          solution="f(di(",
          hint="get onto a paren, then delete INSIDE it",
          why="di( empties the parentheses but keeps them."),
        C(["data = arr[old_index]"], ["data = arr[]"],
          start_cursor=[1, 12], solution="di[",
          hint="empty the subscript but keep the brackets",
          why="di[ clears inside [ ] without removing them."),
      ]),

    S("textobj-paragraph", "Operate on whole paragraphs (dip, dap, cip)",
      "text_object",
      "ip is the INSIDE-paragraph object (the block of non-blank lines); ap is "
      "AROUND (and grabs an adjoining blank line too). dip/dap delete a block, "
      "cip changes it, yip yanks it — all regardless of cursor position within the "
      "paragraph. Linewise cousins of iw/aw.",
      ["dip", "dap", "cip", "yip"], 3, [
        C(["first thought", "still mulling", "", "new idea"], ["", "new idea"],
          solution="dip",
          hint="delete the inner paragraph, leave the blank line",
          why="dip removes the text block without touching the separator."),
        C(["dear diary", "today was long", "", "the end"], ["the end"],
          solution="dap",
          hint="delete AROUND the paragraph, blank line and all",
          why="dap clears the whole stanza plus its trailing blank."),
        C(["rough draft", "messy notes", "", "keep this"],
          ["polished", "", "keep this"],
          solution="cippolished<Esc>",
          hint="change the whole paragraph at once",
          why="cip swaps an entire block for new text in one motion."),
      ]),

    S("motion-match-pair", "Jump between matching pairs (%)", "motion",
      "% jumps between the opening and closing of a matched pair — (), {}, or []. "
      "Land on (or before) one bracket and % flies to its partner, however far "
      "and however nested. It also marks where you jumped from.",
      ["%", "`", "ci(", "d%"], 2, [
        C(["function(a, b, c)"], start_cursor=[1, 9], target=[1, 17],
          solution="%",
          hint="leap from the open paren to its match",
          why="% finds the matching ) no matter what's between."),
        C(["{ outer { inner } tail }"], start_cursor=[1, 1], target=[1, 24],
          solution="%",
          hint="from the outer brace to its partner, past the nested one",
          why="% respects nesting — it skips the inner pair correctly."),
        C(["matrix = [1, 2, 3, 4]"], start_cursor=[1, 10], target=[1, 21],
          solution="%",
          hint="leap from the open bracket to its closing ]",
          why="% matches [ ] too, not just parentheses."),
      ]),

    S("operator-search-motion", "Operate to a search match (d/pat)", "operator",
      "A search is a motion, so it can be the operand of an operator. d/{pat}<CR> "
      "deletes from the cursor up to (not including) the next match — perfect for "
      "excising text up to a landmark without counting words or visual selecting.",
      ["d/", "c/", "y/", "v/"], 4, [
        C(["This phrase takes time but eventually gets here"],
          ["This phrase gets here"],
          solution="2wd/ge<CR>",
          hint="from 'takes', delete up to the search for 'ge'",
          why="d/ge deletes to the match; search is an exclusive motion."),
        C(["keep START middle END keep"], ["keep END keep"],
          solution="fSd/END<CR>",
          hint="delete from START up to END",
          why="An operator + search motion carves out a labelled span."),
      ]),
]
