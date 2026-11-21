"""book.json is the one record every style draws from: it must match the book and the run exactly."""

import json
from pathlib import Path

import pytest

from rebind import source, tokens

RUN = Path(__file__).parents[1] / "out/pride-and-prejudice/runs/20261114T014318Z-qwen3-30b-a3b-instruct-2507-q4-K-M"


def test_longer_names_win_and_are_whole_words():
    names = [("miss darcy", 1), ("darcy", 0), ("eliza", 2)]
    assert tokens._named("Miss Darcy was with Elizabeth.", names) == [1]
    assert tokens._named("Darcy bowed to Miss Darcy and Eliza.", names) == [1, 0, 2]


@pytest.mark.skipif(not (RUN / "settings" / "settings.jsonl").exists(), reason="needs the full-book run")
def test_book_file_matches_the_book_and_the_run(tmp_path):
    book = source.load_book("pride-and-prejudice")
    out = tokens.tokenize(RUN, book, out_dir=tmp_path, log=lambda *_: None)
    B = json.loads((out / "book.json").read_text())
    facts = {f["id"]: f for f in map(json.loads, open(RUN / "facts.jsonl"))}
    S, P = B["sentences"], B["passages"]
    n = len(S["start"])
    assert all(len(col) == n for col in S.values())
    # Sentences are in order, do not overlap, and lie inside their passage.
    for i in range(n):
        p = P[S["passage"][i]]
        assert p["start"] <= S["start"][i] < S["end"][i] <= p["end"]
        assert i == 0 or S["start"][i] >= S["end"][i - 1]
    assert sum(p["sentences"][1] for p in P) == n
    # Every fact a passage carries exists in the run, belongs to that passage, and is counted on its sentences.
    cited = 0
    for p in P:
        ids = [f for who in p["people"] for f in who["facts"]]
        ids += [m["fact"] for kind in ("meetings", "objects", "events") for m in p[kind]]
        ids += [p["tone"]["fact"]] if p["tone"] else []
        assert all(facts[f]["passage"] == p["id"] for f in ids)
        cited += len(ids)
    assert cited > 3000
    # A sentence that names someone really contains one of that person's verified names.
    called = {}
    for f in facts.values():
        if f["type"] == "character":
            called.setdefault(f["data"]["called_here"].casefold().replace("’", "'"), True)
    for i in range(0, n, 37):
        text = book.text[S["start"][i]:S["end"][i]].casefold().replace("’", "'").replace("\r\n", " ")
        if S["people"][i]:
            assert any(c in text for c in called)
        assert S["words"][i] == len(book.text[S["start"][i]:S["end"][i]].split())


def test_a_description_owns_a_column_only_if_the_book_uses_it_as_a_name():
    people = {"Scrooge", "Mr. Darcy"}
    ent = lambda name, kind="reference": {"canonical": name, "kind": kind, "names": [name]}  # noqa: E731
    assert tokens.figure(ent("Scrooge", "person"), people) == "name"
    assert tokens.figure(ent("the Ghost"), people) == "title"
    assert tokens.figure(ent("Scrooge's nephew"), people) == "relation"
    assert tokens.figure(ent("Mr. Darcy’s sister"), people) == "relation"
    for name in ("the clerk", "the fire", "Tom's nephew", "the two eldest"):
        assert tokens.figure(ent(name), people) is None
    assert tokens.figure(ent("the Officers", "group"), people) is None
