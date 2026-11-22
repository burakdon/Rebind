"""The book as a knitting pattern: a scarf anyone can knit, where every row can be unravelled.

A style over book.json (rebind tokenize); no model is called. Knitting sets the terms:
one yarn per row, a width a person can hold, a length a person can finish. So the
whole book is told at passage level, one pair of rows each.

Nothing here rests on a score a person cannot check. The reader labels each sentence
warm, cold or neither, and tense or calm (rebind label). A row's yarn and texture are
counted from those labels by the rules below, so the reason for a row is the sum that
produced it, and anyone can redo it by hand. The book is read twice, in different
words, and the counts are taken over both readings together. Where the two readings,
counted apart, would pick yarns two or more apart, the row is left undyed.

pattern.json holds the rules (K1-K7), the materials, and every pair of rows as chart
symbols and as written instructions, each with its tallies and the facts it rests on.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .source import ROOT

EDGE = 3                 # stitches at each edge that are always knitted
PEOPLE = 10              # columns
UNIT = 3                 # one plain stitch, then the two an eyelet takes
CAST_ON = EDGE + 1 + PEOPLE * UNIT + EDGE          # 37
# Design choices, not learned: fixed after looking at how the first reading's balances
# spread, so that all five yarns are used. Changing them changes the scarf, not the labels.
YARN_CUTS = (-0.5, -0.2, 0.2, 0.5)       # balance = (warm - cold) / sentences
RIDGED_SHARE = 0.5                        # share of sentences labelled tense
# The dye is a design choice too, and the only thing here that differs from book to book. Each book
# names its palette in books/<slug>.json. A palette is five yarns from cold to warm: a dark and a light
# cool colour, a grey, a light and a dark warm colour. All three were checked so that no two yarns, the
# undyed one included, are confused under red-green colour blindness (the first blue-to-red palette failed
# that: its rose and its grey could not be told apart).
PALETTES = {
    "evergreen-gold": {
        "name": "Evergreen and candle gold", "from": "the book's holly and its gold",
        "yarns": [("evergreen", "#12463f"), ("sea green", "#84c8b2"), ("pewter grey", "#868a8c"),
                  ("candle gold", "#deae36"), ("dark amber", "#9c5806")]},
    "violet-marmalade": {
        "name": "Violet and marmalade", "from": "a dream colour, and the jar Alice takes as she falls",
        "yarns": [("deep violet", "#5a3391"), ("lilac", "#b3a0e6"), ("stone grey", "#8f8b82"),
                  ("apricot", "#f2a26a"), ("marmalade", "#bd5015")]},
    "coats": {
        "name": "Blue coat and red coat", "from": "Bingley's blue coat and the officers' red ones",
        "yarns": [("deep blue", "#2c4f96"), ("sky blue", "#8fb3e6"), ("stone grey", "#8f8b82"),
                  ("salmon", "#f0a48e"), ("scarlet", "#a11f2d")]},
}
DEFAULT_PALETTE = "coats"
UNDYED = ("undyed", "#efe6d0")
PALETTE_NOTE = ("The colours are a choice, not a count: no book names colours often enough to count them. "
                "In every palette cold is the cool colour and warm the warm one, and undyed is cream.")


def yarns_of(palette: str) -> list[tuple[str, str, str]]:
    """key, name, colour on screen: A to E from cold to warm, then U."""
    return [(k, name, hx) for k, (name, hx) in zip("ABCDEU", [*PALETTES[palette]["yarns"], UNDYED])]


def palette_for(slug: str) -> str:
    """The palette a book names in its settings file, or the default."""
    f = ROOT / "books" / f"{slug}.json"
    key = json.loads(f.read_text()).get("palette") if f.exists() else None
    return key if key in PALETTES else DEFAULT_PALETTE


UNSURE = "U"
UNSURE_GAP = 2           # yarns apart at which the two readings, counted apart, are taken to disagree
# Worsted-weight yarn on 4.5 mm (US 7) needles. These are ordinary figures for that
# weight, not measurements of this scarf: knit a swatch before trusting the size.
GAUGE = {"stitches_per_4in": 18, "smooth_rows_per_4in": 24, "ridged_rows_per_4in": 36,
         "yarn_inches_per_stitch": 0.85, "needles": "4.5 mm (US 7)", "yarn": "worsted weight",
         "note": "Typical figures for worsted yarn; sizes and yardage are estimates until you swatch."}

a_, b_, c_, d_ = YARN_CUTS
RULES = {
    "K1": "The scarf is knitted from the first chapter to the last. Every passage of the book is one pair of rows: "
          "a right-side row and the row back.",
    "K2": "The reader labels every sentence warm, cold or neither, and does so twice, with the question put in "
          "different words. For a passage, take the warm labels minus the cold ones over both readings and divide "
          f"by the number of labels. Yarn A if that is {a_} or less, B if below {b_}, C if below {c_}, "
          f"D if below {d_}, E otherwise.",
    "K3": "In both readings the reader also labels every sentence tense or calm. If at least "
          f"{round(RIDGED_SHARE * 100)} in 100 of a passage's labels are tense, the row back is knitted, which "
          "leaves a raised ridge you can feel; otherwise it is purled and the fabric is smooth. Three stitches at "
          "each edge are always knitted so the scarf lies flat.",
    "K4": f"The {PEOPLE} most-mentioned people each own a column. The most-mentioned is in the middle and the others "
          "alternate outwards. A person is someone the reader named, or a description the book itself uses as a "
          "name at least three times: one written with a capital (the Ghost), or a named person's relation "
          "(Scrooge's nephew).",
    "K5": "On the right-side row a person's column gets an eyelet (yarn over, knit two together) if the reader has "
          "a verified fact that they are in that passage. Otherwise the column is knitted plain.",
    "K6": "The first passage of every chapter has an eyelet in the edge, so chapters can be counted along one side.",
    "K7": "The two readings are also counted apart. If on their own they would pick yarns two or more apart "
          "(A and C, say), the passage is knitted in undyed yarn U: the answer depends too much on how the "
          "question was put, so the scarf makes no claim.",
}
ONCE = {  # the same rules for a book that has only been read once so far
    "K2": "The reader labels every sentence warm, cold or neither. For a passage, take the warm sentences minus the "
          f"cold ones and divide by the number of sentences. Yarn A if that is {a_} or less, B if below {b_}, "
          f"C if below {c_}, D if below {d_}, E otherwise.",
    "K3": "The reader also labels every sentence tense or calm. If at least "
          f"{round(RIDGED_SHARE * 100)} in 100 of a passage's sentences are tense, the row back is knitted, which "
          "leaves a raised ridge you can feel; otherwise it is purled and the fabric is smooth. Three stitches at "
          "each edge are always knitted so the scarf lies flat.",
    "K7": "The book has been read only once so far, so nothing checks whether the labels depend on how the "
          "question was put. A passage with no usable labels is knitted in undyed yarn U.",
}
# ---- the same scarf in one yarn -------------------------------------------------------------------------
# For a knitter with a single ball of yarn, or a reader who goes by touch. Nothing is decided again: the
# class K2 gives a passage (A to E, or U) and K3's tense or calm are knitted as stitches instead of colours.
#   cold is rough and warm is smooth: the colder the class, the more of the row is purled;
#   a rope of two knit stitches runs up one side and is crossed on a tense passage;
#   a passage the readings disagree on is two plain knitted rows, a flat ridge that says nothing.
ROPE = 4                                   # purl 1, the two rope stitches, purl 1
TX_CAST_ON = CAST_ON + ROPE                # 41
PURLED = {"A": 4, "B": 3, "C": 2, "D": 1, "E": 0}      # stitches purled in every four, on the right side
TX_RULES = {
    "K2": "One yarn. The reader labels every sentence warm, cold or neither, twice, and the count picks a class "
          f"exactly as in the coloured scarf: A if the balance is {a_} or less, B if below {b_}, C if below {c_}, "
          f"D if below {d_}, E otherwise. The class says how much of the right-side row is purled: A all of it, "
          "B three stitches in four, C every other stitch, D one in four, E none. So a cold passage is rough "
          "under the hand and a warm one is smooth. On the row back, work each stitch as it faces you (knit the "
          "knits, purl the purls). The purls shift along on every other passage, so the scarf does not pull in "
          "like ribbing.",
    "K3": "Two knit stitches near one edge make a rope, with a purl stitch on each side of it. If at least "
          f"{round(RIDGED_SHARE * 100)} in 100 of a passage's labels are tense, cross the two (a right twist) on "
          "the right-side row; otherwise knit them straight. So the rope twists where the book is tense. "
          "Three stitches at each edge are always knitted so the scarf lies flat.",
    "K7": "The two readings are also counted apart. If on their own they would pick classes two or more apart "
          "(A and C, say), both rows of the passage are knitted plain, which leaves one flat ridge with no "
          "pattern in it: the scarf makes no claim.",
}
TX_ONCE = {"K7": "The book has been read only once so far, so nothing checks whether the labels depend on how the "
                 "question was put. A passage with no usable labels is two plain knitted rows."}
TX_ABBREVIATIONS = {"RT": "right twist: knit the second stitch on the left needle without slipping it off, "
                          "then knit the first, and slip both off together"}


def texture_row(cells: str, yarn: str, tense: bool, n: int) -> tuple[str, str, str]:
    """One passage in one yarn: the right-side row as chart symbols and in words, and the row back in words.

    `cells` is the coloured scarf's right-side row, whose eyelets are kept where they are. Symbols: k knit,
    p purl, o yarn over, / knit two together, X x the two stitches of a right twist.
    """
    row = list(cells[:CAST_ON - EDGE])
    if yarn != UNSURE:
        for c in range(EDGE, CAST_ON - EDGE):
            if row[c] != "k":
                continue
            # C is knit one, purl one, moved over by one on every other passage; B and D move over by two
            k = (c - EDGE + (n % 2) * (1 if PURLED[yarn] == 2 else 2)) % 4
            purl = {0: False, 1: k == 0, 2: k % 2 == 0, 3: k != 0, 4: True}[PURLED[yarn]]
            if purl:
                row[c] = "p"
    rs = "".join(row) + "p" + ("Xx" if tense else "kk") + "p" + "k" * EDGE
    # the row back, read from the other edge: a stitch knitted on the right side is purled, and so on
    back = []
    for c in range(TX_CAST_ON - 1, -1, -1):
        inner = EDGE <= c < CAST_ON - EDGE
        back.append("k" if c < EDGE or c >= TX_CAST_ON - EDGE or rs[c] == "p" or (inner and yarn == UNSURE) else "p")
    return rs, written_tx(rs), written_tx("".join(back))


def written_tx(cells: str) -> str:
    """Chart symbols as words, with runs of knit and purl counted."""
    out, i = [], 0
    while i < len(cells):
        ch = cells[i]
        if ch in "kp":
            j = i
            while j < len(cells) and cells[j] == ch:
                j += 1
            out.append(f"{ch}{j - i}")
            i = j
        elif ch == "X":
            out.append("RT")
            i += 2
        else:
            out.append("yo" if ch == "o" else "k2tog")
            i += 1
    return ", ".join(out)


ABBREVIATIONS = {"k": "knit", "p": "purl", "yo": "yarn over", "k2tog": "knit two together",
                 "RS": "right side", "WS": "wrong side"}


def yarn_for(balance: float) -> str:
    a, b, c, d = YARN_CUTS
    return "A" if balance <= a else "B" if balance < b else "C" if balance < c else "D" if balance < d else "E"


def tally(feeling: list[int], pace: list[int]) -> dict | None:
    """Count one passage's sentence labels (feeling 1 warm, 2 cold, 0 neither; pace 1 tense). None if unread."""
    if not feeling or -1 in feeling or -1 in pace:
        return None
    n, warm, cold, tense = len(feeling), feeling.count(1), feeling.count(2), pace.count(1)
    balance = (warm - cold) / n
    return {"n": n, "warm": warm, "cold": cold, "neither": n - warm - cold, "tense": tense,
            "balance": round(balance, 3), "yarn": yarn_for(balance), "ridged": tense / n >= RIDGED_SHARE}


def margin(t: dict) -> int | None:
    """Fewest feeling labels that would have to change for K2 to pick another yarn."""
    for k in range(1, t["n"] + 1):
        up = 2 * min(k, t["cold"]) + min(max(0, k - t["cold"]), t["neither"])      # cold->warm, then neither->warm
        down = 2 * min(k, t["warm"]) + min(max(0, k - t["warm"]), t["neither"])
        if any(yarn_for((t["warm"] - t["cold"] + d) / t["n"]) != t["yarn"] for d in (up, -down)):
            return k
    return None


def written(cells: str) -> str:
    """Chart symbols for a right-side row ('k', 'o' yarn over, '/' knit two together) as words."""
    out, run = [], 0
    for ch in cells:
        if ch == "k":
            run += 1
            continue
        if run:
            out.append(f"k{run}")
            run = 0
        out.append("yo" if ch == "o" else "k2tog")
    if run:
        out.append(f"k{run}")
    return ", ".join(out)


def stitches_after(cells: str) -> int:
    """Stitches on the needle after working the row: an eyelet makes one and takes one."""
    return cells.count("k") + cells.count("o") + cells.count("/")


LEAD_BOOK = "a-christmas-carol"   # shown first on the front page and large on the poster


def shelf(data_dir: Path) -> Path:
    """books.json: every book that has a pattern, the lead book first and then shortest first."""
    books = []
    for f in sorted(Path(data_dir).glob("*/pattern.json")):
        K = json.loads(f.read_text())
        books.append({"slug": K["book"]["slug"], "title": K["book"]["title"], "author": K["book"].get("author"),
                      "chapter_word": K["book"].get("chapter_word") or "Chapter", "model": K["run"]["model"],
                      **{k: K["size"][k] for k in ("pairs", "rows", "width_in", "length_in")},
                      "yards": sum(y["yards"] for y in K["yarns"]), "palette": K.get("palette", {}).get("key", DEFAULT_PALETTE),
                      "undyed": sum(r["unsure"] for r in K["rows"]), "people": [c["name"] for c in K["columns"]]})
    books.sort(key=lambda b: (b["slug"] != LEAD_BOOK, b["pairs"]))
    (Path(data_dir) / "books.json").write_text(json.dumps(books, indent=1, ensure_ascii=False))
    # palettes.json: every palette, so the site can show any book in any of them.
    (Path(data_dir) / "palettes.json").write_text(json.dumps({"note": PALETTE_NOTE, "palettes": [
        {"key": key, "name": P["name"], "from": P["from"],
         "yarns": [{"key": k, "name": name, "hex": hx} for k, name, hx in yarns_of(key)]}
        for key, P in PALETTES.items()]}, indent=1, ensure_ascii=False))
    return Path(data_dir) / "books.json"


def knit(book_json: Path, out_dir: Path | None = None, log=print) -> Path:
    B = json.loads(Path(book_json).read_text())
    S = B["sentences"]
    twice = B.get("readings", {}).get("b", 0) > 0
    people = B["people"][:PEOPLE]
    # K4: most mentioned in the middle, the rest alternating outwards.
    lane = {p["id"]: ((i + 1) // 2) * (1 if i % 2 else -1) for i, p in enumerate(people)}
    across = sorted(people, key=lambda p: lane[p["id"]])
    unit_of = {p["id"]: j for j, p in enumerate(across)}
    first_cell = lambda j: EDGE + 1 + j * UNIT  # noqa: E731  (the yarn over; the k2tog is the next cell)
    columns = [{"person": p["id"], "name": p["name"], "mentions": p["mentions"], "as": p.get("as", "name"),
                "stitches": [first_cell(j) + 1, first_cell(j) + 2]} for j, p in enumerate(across)]

    rows, seen_chapter, used = [], set(), Counter()
    for n, p in enumerate(B["passages"], 1):
        cells = ["k"] * CAST_ON
        starts = p["chapter"] not in seen_chapter
        seen_chapter.add(p["chapter"])
        if starts:  # K6
            cells[1], cells[2] = "o", "/"
        here = [q for q in p["people"] if q["id"] in unit_of]
        for q in here:  # K5
            c = first_cell(unit_of[q["id"]])
            cells[c], cells[c + 1] = "o", "/"
        cells = "".join(cells)
        s0, sn = p["sentences"]
        ta = tally(S["feeling"][s0:s0 + sn], S["pace"][s0:s0 + sn])
        tb = tally(S["feeling_b"][s0:s0 + sn], S["pace_b"][s0:s0 + sn]) if twice else None
        # K2, K3: count over both readings together. K7: undyed if, apart, they are too far from each other.
        both = tally(S["feeling"][s0:s0 + sn] + S["feeling_b"][s0:s0 + sn],
                     S["pace"][s0:s0 + sn] + S["pace_b"][s0:s0 + sn]) if twice else ta
        gap = abs("ABCDE".index(ta["yarn"]) - "ABCDE".index(tb["yarn"])) if ta and tb else None
        unsure = both is None or (twice and gap >= UNSURE_GAP)
        yarn = UNSURE if unsure else both["yarn"]
        ridged = bool(both and both["ridged"])
        used[yarn] += 1
        rows.append({
            "n": n, "passage": p["id"], "chapter": p["chapter"],
            "chapter_label": B["chapters"][p["chapter"] - 1]["label"], "starts_chapter": starts,
            "yarn": yarn, "unsure": unsure, "texture": "ridged" if ridged else "smooth",
            "tally": {"a": ta, "b": tb, "both": both}, "gap": gap, "margin": margin(both) if both else None,
            "rs": cells, "rs_text": written(cells),
            "ws_text": f"k{CAST_ON}" if ridged else f"k{EDGE}, p{CAST_ON - 2 * EDGE}, k{EDGE}",
            "tx": dict(zip(("rs", "rs_text", "ws_text"), texture_row(cells, yarn, ridged, n))),
            "eyelets": [{"person": q["id"], "called": q["called"], "facts": q["facts"], "spans": q["spans"]} for q in here],
        })

    g = GAUGE
    smooth = sum(1 for r in rows if r["texture"] == "smooth")
    ridged = len(rows) - smooth
    length = smooth * 2 * 4 / g["smooth_rows_per_4in"] + ridged * 2 * 4 / g["ridged_rows_per_4in"]
    yards = lambda pairs: round(pairs * 2 * CAST_ON * g["yarn_inches_per_stitch"] / 36 * 1.1)  # noqa: E731
    cuts = [None, *YARN_CUTS, None]
    palette = palette_for(B["book"]["slug"])
    doc = {
        "book": B["book"], "run": B["run"], "generated": datetime.now(timezone.utc).isoformat(),
        "rules": {k: v.replace("chapter", (B["book"].get("chapter_word") or "chapter").lower())
                  for k, v in {**RULES, **({} if twice else ONCE)}.items()},
        "abbreviations": ABBREVIATIONS, "gauge": g,
        "cast_on": CAST_ON, "edge": EDGE, "yarn_cuts": list(YARN_CUTS), "ridged_share": RIDGED_SHARE,
        "unsure_gap": UNSURE_GAP,
        "readings": {"twice": twice, "unread": sum(r["tally"]["a"] is None for r in rows)},
        "columns": columns, "chapter_stitches": [2, 3],
        "palette": {"key": palette, "name": PALETTES[palette]["name"], "from": PALETTES[palette]["from"],
                    "note": PALETTE_NOTE},
        "yarns": [{"key": k, "name": name, "hex": hx, "pairs": used[k], "yards": yards(used[k]),
                   "balance": [cuts[i], cuts[i + 1]] if k != UNSURE else None}
                  for i, (k, name, hx) in enumerate(yarns_of(palette))],
        "size": {"width_in": round(CAST_ON * 4 / g["stitches_per_4in"], 1), "length_in": round(length),
                 "pairs": len(rows), "rows": 2 * len(rows), "stitches": 2 * len(rows) * CAST_ON,
                 "smooth_pairs": smooth, "ridged_pairs": ridged},
        "texture": {
            "cast_on": TX_CAST_ON, "rope_stitches": [CAST_ON - EDGE + 2, CAST_ON - EDGE + 3],
            "rules": {k: v.replace("chapter", (B["book"].get("chapter_word") or "chapter").lower())
                      for k, v in {**TX_RULES, **({} if twice else TX_ONCE)}.items()},
            "abbreviations": TX_ABBREVIATIONS, "purled_in_four": PURLED,
            "yarn": {"name": "one light, smooth yarn", "hex": "#e9dcc0",
                     "note": "Texture shows best in a light, plain yarn; a dark or fuzzy one hides it."},
            "size": {"width_in": round(TX_CAST_ON * 4 / g["stitches_per_4in"], 1),
                     "length_in": round(sum(2 * 4 / g["ridged_rows_per_4in" if r["unsure"] else "smooth_rows_per_4in"]
                                            for r in rows)),
                     "stitches": 2 * len(rows) * TX_CAST_ON, "twisted_pairs": sum(r["texture"] == "ridged" for r in rows),
                     "yards": round(len(rows) * 2 * TX_CAST_ON * g["yarn_inches_per_stitch"] / 36 * 1.1)},
        },
        "rows": rows,
    }
    out = Path(out_dir or ROOT / "site" / "data" / B["book"]["slug"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "pattern.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    shelf(out.parent)
    s = doc["size"]
    log(f"cast on {CAST_ON}, {s['pairs']} pairs of rows ({smooth} smooth, {ridged} ridged), about "
        f"{s['width_in']} x {s['length_in']} in, {sum(y['yards'] for y in doc['yarns'])} yd: "
        + ", ".join(f"{y['key']} {y['pairs']}" for y in doc["yarns"])
        + (f"; {doc['readings']['unread']} passages not labelled yet" if doc["readings"]["unread"] else "")
        + f" -> {out / 'pattern.json'}")
    return out
