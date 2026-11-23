"""The scarf in Alize Puffy: eight finger-knitted loops a row, neighbouring passages counted together."""

import json

import pytest

from rebind import knit
from rebind.source import ROOT

BOOKS = sorted(p.parent.name for p in (ROOT / "site" / "data").glob("*/pattern.json"))


def test_a_row_is_eight_loops_and_says_its_class():
    for cls, reverse in knit.PURLED.items():
        for tense in (False, True):
            cells = knit.puffy_cells(cls, tense)
            assert len(cells) == knit.PUFFY_LOOPS
            assert cells[0] == cells[-1] == "k"                              # P4: the edges
            assert cells[1:5] == "p" * reverse + "k" * (4 - reverse)         # P2: the feeling, counted from loop 2
            assert cells[5:7] == ("Xx" if tense else "kk")                   # P3: the pair
    assert knit.puffy_cells(knit.UNSURE, True) == knit.puffy_cells(knit.UNSURE, False) == "p" * 8     # P5


def test_no_two_classes_look_alike():
    looks = {knit.puffy_cells(c, t) for c in "ABCDE" for t in (False, True)} | {knit.puffy_cells(knit.UNSURE, False)}
    assert len(looks) == 11


def test_written_rows_use_up_eight_loops():
    for cls in "ABCDE" + knit.UNSURE:
        for tense in (False, True):
            text = knit.written_puffy(knit.puffy_cells(cls, tense))
            assert sum(int(part.split()[-1]) for part in text.split(", ")) == knit.PUFFY_LOOPS
    assert knit.written_puffy("kpppkXxk") == "normal 1, reverse 3, normal 1, cross 2, normal 1"


def test_rows_never_cross_a_chapter_and_miss_no_passage():
    chapters = [1] * 7 + [2] * 1 + [3] * 12 + [4] * 5
    most, groups = knit.puffy_groups(chapters, most=14)
    assert [i for g in groups for i in g] == list(range(len(chapters)))       # every passage once, in order
    assert all(len({chapters[i] for i in g}) == 1 for g in groups)
    assert len(groups) <= 14 and most == max(len(g) for g in groups)
    # no shorter run would have fitted
    assert len(knit.puffy_groups(chapters, most=10 ** 6)[1]) == len(chapters)
    if most > 1:
        fewer = sum(-(-n // (most - 1)) for n in (7, 1, 12, 5))
        assert fewer > 14


def test_a_book_with_more_chapters_than_rows_gets_a_row_a_chapter():
    most, groups = knit.puffy_groups([1, 1, 2, 2, 2, 3], most=2)
    assert groups == [[0, 1], [2, 3, 4], [5]] and most == 3


@pytest.mark.parametrize("slug", BOOKS)
def test_every_published_row_is_what_its_labels_count_to(slug):
    K = json.loads((ROOT / "site" / "data" / slug / "pattern.json").read_text())
    B = json.loads((ROOT / "site" / "data" / slug / "book.json").read_text())
    P, S, at = K["puffy"], B["sentences"], {p["id"]: p for p in B["passages"]}
    assert len(P["rows"]) <= knit.PUFFY_MAX_ROWS
    assert [i for r in P["rows"] for i in r["passages"]] == [p["id"] for p in B["passages"]]
    for r in P["rows"]:
        assert len({at[i]["chapter"] for i in r["passages"]}) == 1
        idx = [i for q in r["passages"] for i in range(at[q]["sentences"][0], sum(at[q]["sentences"]))]
        feeling = [S[k][i] for k in ("feeling", "feeling_b") for i in idx if S[k][i] >= 0]
        pace = [S[k][i] for k in ("pace", "pace_b") for i in idx if S[k][i] >= 0]
        both = r["tally"]["both"]
        assert both["n"] == len(feeling) and both["warm"] == feeling.count(1) and both["cold"] == feeling.count(2)
        assert both["yarn"] == knit.yarn_for((both["warm"] - both["cold"]) / both["n"])
        assert r["tense"] == (pace.count(1) / len(pace) >= knit.RIDGED_SHARE)
        assert r["unsure"] == (r["gap"] >= knit.UNSURE_GAP) and r["yarn"] == (knit.UNSURE if r["unsure"] else both["yarn"])
        assert r["cells"] == knit.puffy_cells(r["yarn"], r["tense"]) and r["text"] == knit.written_puffy(r["cells"])
        # the row's pairs are the coloured scarf's rows for the same passages
        assert [K["rows"][n - 1]["passage"] for n in r["pairs"]] == [r["passages"][0], r["passages"][-1]]
