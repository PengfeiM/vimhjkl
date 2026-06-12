"""Patterns and literals: the magic switches.

Pattern switches are best drilled through substitutions that only work with the
right switch.  Solutions use raw strings because they contain backslashes.
"""

from build.common import C, S

SKILLS = [
    S("regex-very-magic", "Very magic regex (\\v)", "search_replace",
      "Put \\v at the start of a pattern for 'very magic' mode: every "
      "non-alphanumeric (besides _) is special, so (), |, +, {} work WITHOUT "
      "backslashes — just like Perl/Python regex. It turns Vim's escape-heavy "
      "default syntax into something readable.",
      [r"\v", r"\d", r"(a|b)", r"+"], 4, [
        C(["call 555 then 7000 or 42 today"], ["call # then # or # today"],
          solution=r":%s/\v\d+/#/g<CR>",
          hint=r"\v lets \d+ match digit runs without escaping the +",
          why=r"In default magic mode you'd need \d\+; \v cleans it up."),
        C(["logo.png hero.jpg icon.png"], ["logo.webp hero.webp icon.webp"],
          solution=r":%s/\v(png|jpg)/webp/g<CR>",
          hint=r"\v makes ( ) and | special with no backslashes",
          why=r"Alternation reads naturally under \v: migrate (png|jpg) at once."),
      ]),

    S("regex-very-nomagic", "Verbatim search (\\V)", "search_replace",
      "When you want to match text literally, \\V ('very nomagic') strips the "
      "special meaning from . * $ and friends, so they match themselves. Ideal "
      "for paths, version strings, or anything full of regex metacharacters.",
      [r"\V", ".", "$", "*"], 4, [
        C(["a.b.c matches", "axbxc also"], ["DOT matches", "axbxc also"],
          solution=r":%s/\Va.b.c/DOT/<CR>",
          hint=r"\V makes the dots literal so axbxc is NOT matched",
          why=r"Without \V, a.b.c would also hit 'axbxc' (. = any char)."),
        C(["pay $5.00 now"], ["pay DONE now"],
          solution=r":%s/\V$5.00/DONE/<CR>",
          hint=r"\V treats $ and . as ordinary characters",
          why=r"\V lets you match currency/decimals without escaping each one."),
        # Without \V the [0] is a character class, so /data[0]/ would also
        # match the bare 'data0' on line 2 — the decoy proves the point.
        C(["total += data[0]", "weights = data0 * scale",
           "print(data[0], total)"],
          ["total += data[i]", "weights = data0 * scale",
           "print(data[i], total)"],
          solution=r":%s/\Vdata[0]/data[i]/g<CR>",
          hint=r"\V keeps the [0] literal — otherwise it's a character class",
          why=r"Plain /data[0]/ matches 'data0' too; \V pins the brackets down."),
      ]),

    S("regex-case-toggle", "Case-insensitive match (\\c)", "search_replace",
      "Tack \\c anywhere in a pattern to force a case-INsensitive match (\\C "
      "forces sensitive), regardless of your 'ignorecase' setting. Handy for "
      "catching a word however it's capitalised.",
      [r"\c", r"\C", "ignorecase", "smartcase"], 3, [
        C(["The CAT sat, a cat ran, the Cat napped"],
          ["The dog sat, a dog ran, the dog napped"],
          solution=r":%s/cat\c/dog/g<CR>",
          hint=r"\c makes the match ignore case for the whole pattern",
          why=r"One \c catches CAT, cat and Cat in a single substitute."),
      ]),
]
