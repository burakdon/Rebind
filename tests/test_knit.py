"""The pattern must be knittable, and every row must be the sum of labels a person can check."""

import json
from pathlib import Path

import pytest

from rebind import knit, source, tokens

RUN = Path(__file__).parents[1] / "out/pride-and-prejudice/runs/20261114T014318Z-qwen3-30b-a3b-instruct-2507-q4-K-M"


def test_rows_are_written_as_a_knitter_reads_them():
    assert knit.written("kkkokkko/k") == "k3, yo, k3, yo, k2tog, k1"
    assert knit.written("k" * 37) == "k37"


def test_the_yarn_is_a_sum_anyone_can_redo():
    a, b, c, d = knit.YARN_CUTS
    assert [knit.yarn_for(x) for x in (-1, a, (a + b) / 2, b, 0, c, (c + d) / 2, d, 1)] == list("AABCCDDEE")
    # 10 sentences: 6 warm, 1 cold, 3 neither; 4 tense.
    t = knit.tally([1, 1, 1, 1, 1, 1, 2, 0, 0, 0], [1, 1, 1, 1, 0, 0, 0, 0, 0, 0])
    assert (t["warm"], t["cold"], t["neither"], t["tense"], t["balance"]) == (6, 1, 3, 4, 0.5)
    assert t["yarn"] == knit.yarn_for(0.5) and t["ridged"] == (0.4 >= knit.RIDGED_SHARE)
    assert knit.tally([1, -1], [0, 0]) is None and knit.tally([], []) is None


def test_the_margin_is_the_fewest_labels_that_would_change_the_yarn():
    for feeling in ([1] * 6 + [2] + [0] * 3, [0] * 12, [2] * 5 + [1] * 5, [1] * 9):
        t = knit.tally(feeling, [0] * len(feeling))
        m = knit.margin(t)
        # Brute force: relabel k sentences in the most helpful way, in either direction.
        def moved(k, to):
            f = sorted(feeling, key=lambda v: {1: 2, 0: 1, 2: 0}[v] if to == 2 else {2: 2, 0: 1, 1: 0}[v], reverse=True)
            f = [to if i < k and v != to else v for i, v in enumerate(f)]
            return knit.tally(f, [0] * len(f))["yarn"] != t["yarn"]
        best = next((k for k in range(1, len(feeling) + 1) if moved(k, 1) or moved(k, 2)), None)
        assert m == best


@pytest.mark.skipif(not (RUN / "labels" / "a" / "labels.jsonl").exists(), reason="needs the labelled run")
def test_every_stitch_comes_from_the_reading(tmp_path):
    book = source.load_book("pride-and-prejudice")
    tokens.tokenize(RUN, book, out_dir=tmp_path, log=lambda *_: None)
    out = knit.knit(tmp_path / "book.json", out_dir=tmp_path, log=lambda *_: None)
    K = json.loads((out / "pattern.json").read_text())
    B = json.loads((tmp_path / "book.json").read_text())
    S = B["sentences"]
    facts = {f["id"]: f for f in map(json.loads, open(RUN / "facts.jsonl"))}
    column = {c["person"]: c["stitches"] for c in K["columns"]}
    assert len(K["rows"]) == len(B["passages"]) == K["size"]["pairs"]
    assert sum(r["starts_chapter"] for r in K["rows"]) == len(B["chapters"])
    for r, p in zip(K["rows"], B["passages"]):
        cells = r["rs"]
        # Knittable: the stitch count never changes, and every yarn over is followed by its decrease.
        assert len(cells) == K["cast_on"] == knit.stitches_after(cells)
        assert cells.count("o") == cells.count("/") and "o/" * cells.count("o") == "".join(c for c in cells if c != "k")
        assert all(c == "k" for c in cells[-K["edge"]:])
        # Traceable: an eyelet is there if and only if a verified character fact of this passage puts the person here.
        holes = {i + 1 for i, c in enumerate(cells) if c == "o"}
        expect = {column[e["person"]][0] for e in r["eyelets"]} | ({K["chapter_stitches"][0]} if r["starts_chapter"] else set())
        assert holes == expect
        for e in r["eyelets"]:
            assert e["facts"] and all(facts[f]["passage"] == p["id"] and facts[f]["type"] == "character" for f in e["facts"])
        assert {e["person"] for e in r["eyelets"]} == {q["id"] for q in p["people"]} & set(column)
        # Explainable: the yarn and the ridge are exactly what the rules make of this passage's sentence labels.
        s0, n = p["sentences"]
        ta = knit.tally(S["feeling"][s0:s0 + n], S["pace"][s0:s0 + n])
        tb = knit.tally(S["feeling_b"][s0:s0 + n], S["pace_b"][s0:s0 + n])
        assert r["tally"]["a"] == ta
        if ta:
            assert ta["warm"] + ta["cold"] + ta["neither"] == ta["n"] == n
        if K["readings"]["twice"]:
            assert r["tally"]["b"] == tb
            # K2, K3: both readings counted together. K7: undyed when, apart, they are two or more yarns from each other.
            both = knit.tally(S["feeling"][s0:s0 + n] + S["feeling_b"][s0:s0 + n], S["pace"][s0:s0 + n] + S["pace_b"][s0:s0 + n])
            assert r["tally"]["both"] == both
            if both:
                assert both["n"] == 2 * n and both["warm"] == ta["warm"] + tb["warm"] and both["tense"] == ta["tense"] + tb["tense"]
                gap = abs("ABCDE".index(ta["yarn"]) - "ABCDE".index(tb["yarn"]))
                assert r["gap"] == gap and r["unsure"] == (gap >= knit.UNSURE_GAP)
                assert r["yarn"] == ("U" if r["unsure"] else both["yarn"])
                # the yarn of both together is never outside what the two readings pick apart
                assert sorted([ta["yarn"], both["yarn"], tb["yarn"]])[1] == both["yarn"]
                assert (r["texture"] == "ridged") == both["ridged"] and r["margin"] == knit.margin(both)
            else:
                assert r["yarn"] == "U" and r["unsure"] and r["texture"] == "smooth"
    assert sum(y["pairs"] for y in K["yarns"]) == len(K["rows"])
