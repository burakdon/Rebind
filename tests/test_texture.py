"""The scarf in one yarn: the same decisions as the coloured scarf, knitted as stitches instead of colours."""

import json
import re

from rebind import knit
from rebind.source import ROOT

PLAIN = "k" * knit.CAST_ON
FIELD = slice(knit.EDGE, knit.CAST_ON - knit.EDGE)


def count(text: str) -> int:
    """Stitches a written row uses up: k3 and p3 take three, a right twist two, k2tog two, a yarn over none."""
    n = 0
    for word in text.split(", "):
        m = re.fullmatch(r"([kp])(\d+)", word)
        n += int(m.group(2)) if m else {"RT": 2, "k2tog": 2, "yo": 0}[word]
    return n


def test_the_colder_the_class_the_more_of_the_row_is_purled():
    for n in (1, 2):
        purls = [knit.texture_row(PLAIN, y, False, n)[0][FIELD].count("p") for y in "ABCDE"]
        assert purls == sorted(purls, reverse=True) and len(set(purls)) == 5
        assert purls[0] == knit.CAST_ON - 2 * knit.EDGE and purls[-1] == 0
        assert abs(purls[2] - purls[0] / 2) <= 1          # C: every other stitch


def test_the_purls_move_along_so_the_scarf_does_not_rib():
    for y in "BCD":
        assert knit.texture_row(PLAIN, y, False, 1)[0][FIELD] != knit.texture_row(PLAIN, y, False, 2)[0][FIELD]


def test_the_rope_is_crossed_on_a_tense_passage_and_only_then():
    calm, tense = (knit.texture_row(PLAIN, "C", t, 1) for t in (False, True))
    assert calm[0][knit.CAST_ON - knit.EDGE:] == "pkkpkkk" and tense[0][knit.CAST_ON - knit.EDGE:] == "pXxpkkk"
    assert "RT" in tense[1] and "RT" not in calm[1]


def test_a_passage_the_readings_disagree_on_is_two_plain_knitted_rows():
    rs, _, ws = knit.texture_row(PLAIN, knit.UNSURE, False, 1)
    assert "p" not in rs[FIELD] and ws == f"k{knit.EDGE + 1}, p2, k{knit.CAST_ON - knit.EDGE + 1}"


def test_every_published_row_can_be_knitted_and_says_what_the_coloured_one_says():
    for f in (ROOT / "site" / "data").glob("*/pattern.json"):
        K = json.loads(f.read_text())
        W = K["texture"]["cast_on"]
        assert W == knit.TX_CAST_ON
        for r in K["rows"]:
            rs = r["tx"]["rs"]
            # every row uses up the 41 stitches of the row before and leaves 41: a yarn over makes the stitch its k2tog takes
            assert len(rs) == W and count(r["tx"]["rs_text"]) == W and count(r["tx"]["ws_text"]) == W
            assert all(rs[i + 1] == "/" for i, ch in enumerate(rs) if ch == "o")
            # the holes are where the coloured scarf has them: the same people, the same chapter marks
            assert [i for i, ch in enumerate(rs) if ch in "o/"] == [i for i, ch in enumerate(r["rs"]) if ch in "o/"]
            assert ("X" in rs) == (r["texture"] == "ridged")
            free = [ch for ch in rs[FIELD] if ch in "kp"]
            want = 0 if r["unsure"] else knit.PURLED[r["yarn"]] / 4
            assert abs(free.count("p") / len(free) - want) <= 0.15, (f.parent.name, r["n"])
        assert K["texture"]["size"]["twisted_pairs"] == K["size"]["ridged_pairs"]
