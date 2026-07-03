"""Marks and jumps.

Most of this chapter is cross-file or window-scoped and outside a single-buffer
grader: the jump list (<C-o>/<C-i>), change list (g;/g,/gi), go-to-file (gf),
and global marks (mM/`M) are covered as reference. Within-buffer marks ARE
gradeable, especially as range endpoints for Ex commands.
"""

from build.common import C, S

SKILLS = [
    S("marks-set-and-snap", "Set a mark and snap back (m, `)", "motion",
      "m{a-z} drops a named mark at the cursor (invisible, but there). `{mark} "
      "leaps the cursor straight back to that exact line and column from anywhere "
      "in the buffer; '{mark} goes to the line's first non-blank. Marks are the "
      "fastest way to bookmark a spot before wandering off.",
      ["ma", "`a", "'a", "``"], 3, [
        C(["def fetch_user(user_id):", "    row = db.query(user_id)",
           "    if row is None:", "        raise NotFound(user_id)",
           "    return User.from_row(row)"],
          start_cursor=[1, 5], target=[1, 5], via=5,
          solution="maG`a",
          hint="mark the signature, glance at the return, snap back",
          why="`a jumps to the exact spot you marked."),
        C(["import logging", "logger = logging.getLogger(__name__)",
           "def process(items):", "    for it in items:",
           "        logger.debug(it)", "    return len(items)"],
          start_cursor=[1, 1], target=[1, 1], via=6,
          solution="G``",
          hint="jump to the bottom with G, then `` back",
          why="`` returns to where you were before the last jump."),
        C(["class Cache:", "    def get(self, key):",
           "        return self.store.get(key)", "    def set(self, key, val):",
           "        self.store[key] = val"],
          start_cursor=[2, 5], target=[2, 5], via=1,
          solution="magg'a",
          hint="mark the method, jump to the top, then 'a back",
          why="'a returns to the marked line's first non-blank."),
        # The far version: you're editing mid-function, dive to the constants
        # at the very bottom to check a value, then snap back — across enough
        # distance that scrolling back by eye would lose the exact spot.
        C(["def charge(order):", "    total = order.subtotal",
           "    total += total * TAX_RATE", "    if order.express:",
           "        total += EXPRESS_FEE", "    if total > FREE_SHIP_OVER:",
           "        total -= order.shipping", "    return round(total, 2)", "",
           "def refund(order):", "    ledger.reverse(order.id)",
           "    notify(order.user)", "", "# pricing constants",
           "TAX_RATE = 0.0825", "EXPRESS_FEE = 14.50", "FREE_SHIP_OVER = 120.00"],
          start_cursor=[5, 9], target=[5, 9], via=17,
          solution="maG`a",
          hint="ma where you're editing, G to check the constants, `a back",
          why="Twelve lines away and back to the exact column in two "
              "keystrokes — no scroll-and-hunt."),
        # `` round trip after a search jump: the mark is automatic.
        C(["def render(rows):", "    out = []",
           "    for r in rows:", "        cells = [fmt(c) for c in r]",
           "        out.append(' | '.join(cells))", "    return '\\n'.join(out)",
           "", "def fmt(value):", "    if value is None:",
           "        return '-'", "    if isinstance(value, float):",
           "        return f'{value:.2f}'", "    return str(value)", "",
           "WIDTH_LIMIT = 96"],
          start_cursor=[4, 18], target=[4, 18], via=15,
          solution="/WIDTH<CR>``",
          hint="search to the constant far below, then `` snaps you home",
          why="Every jump sets the previous-position mark for free — `` is "
              "the return ticket you didn't have to buy."),
      ]),

    S("marks-as-ex-range", "Use marks as an Ex range ('a,'b)", "ex_command",
      "Marks make great range endpoints. Drop 'a at the top of a region and 'b at "
      "the bottom, then any Ex command can act on :'a,'b — delete, substitute, "
      "normal, whatever. It beats counting lines for a far-apart range.",
      [":'a,'b", "ma", "mb", ":'a,'bd"], 4, [
        # You DON'T count lines to a far-off boundary — you search to each end and
        # mark it there.  The span is long enough that counting it by eye is a
        # genuine chore; the fence markers make /search the honest way in.
        C(["release checklist", "  bump the version tag",
           "  regenerate the changelog", "TODO-START",
           "  ask the cat for approval", "  rename everything twice",
           "  break the build on purpose", "  blame the intern",
           "  add a blockchain somewhere", "  rewrite it in rust over lunch",
           "  delete the tests that disagree", "  promise it works this time",
           "TODO-END", "  tag the release", "  ship it and hope"],
          ["release checklist", "  bump the version tag",
           "  regenerate the changelog", "  tag the release",
           "  ship it and hope"],
          solution="/TODO-START<CR>ma/TODO-END<CR>mb:'a,'bd<CR>",
          hint="search to each TODO marker, drop a mark there, delete the span",
          why="Marks set at search landings beat counting lines to a far boundary.",
          why_not="10dd means first counting ten lines by eye; a visual V needs "
                  "you to ride j down the whole span. The marks never miscount."),
        # Range must BITE: a whole-file :normal would comment the banners too, so
        # you fence just the code lines with marks — and there are enough of them
        # that counting j's to the far end is no longer the easy way.
        C(["banner: generated header - do not touch", "def conjure():",
           "    return spell", "def banish():", "    return void",
           "def transmute(base):", "    return gold(base)", "def scry(name):",
           "    return mirror[name]", "def dispel(ward):", "    ward.clear()",
           "banner: generated footer - also not yours"],
          ["banner: generated header - do not touch", "# def conjure():",
           "    # return spell", "# def banish():", "    # return void",
           "# def transmute(base):", "    # return gold(base)", "# def scry(name):",
           "    # return mirror[name]", "# def dispel(ward):", "    # ward.clear()",
           "banner: generated footer - also not yours"],
          solution="jma/footer<CR>kmb:'a,'bnormal I# <CR>",
          hint="mark the first code line, search to the footer, mark the last, "
               ":normal only that range",
          why="A whole-file :normal would comment the banners — marks fence it in.",
          why_not=":2,11normal works if you trust yourself to read '11' off a "
                  "screen with no line numbers; the marks land exactly where "
                  "the search does."),
        # The range has to be NECESSARY or the move is pointless: 'old' appears
        # a dozen times inside the [hosts] block AND in [fallback] below it.
        # A bare :%s/old/new/g would clobber the fallback too — so you bracket the
        # block with marks and substitute only :'a,'b.  The block is far too long
        # to count, which is what makes marks the shortest correct path.
        C(["[hosts]", "web01 = old", "web02 = old", "web03 = old",
           "web04 = old", "api01 = old", "api02 = old", "db01 = old",
           "db02 = old", "cache01 = old", "cache02 = old", "queue01 = old",
           "queue02 = old", "[fallback]", "spare01 = old", "spare02 = old",
           "spare03 = old"],
          ["[hosts]", "web01 = new", "web02 = new", "web03 = new",
           "web04 = new", "api01 = new", "api02 = new", "db01 = new",
           "db02 = new", "cache01 = new", "cache02 = new", "queue01 = new",
           "queue02 = new", "[fallback]", "spare01 = old", "spare02 = old",
           "spare03 = old"],
          solution="jma/fallback<CR>kmb:'a,'bs/old/new/g<CR>",
          hint="mark the first host, search to [fallback], mark the line above, "
               "substitute only that range",
          why="Marks scope the :s to the block so the fallback's 'old' survives.",
          why_not=":%s/old/new/g flips the three spares you were keeping; "
                  ":2,13s means counting twelve entries and hoping — the marks "
                  "sit exactly where /fallback landed you."),
      ]),
]
