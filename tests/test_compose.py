"""The map's promise: every mark rests on facts that exist in the run, by a stated rule."""

import json
from pathlib import Path

import pytest

from rebind import compose, source

RUN = Path(__file__).parents[1] / "out/pride-and-prejudice/runs/20261114T014318Z-qwen3-30b-a3b-instruct-2507-q4-K-M"


@pytest.mark.skipif(not (RUN / "settings" / "settings.jsonl").exists(), reason="needs the full-book run")
def test_every_mark_cites_real_facts_and_a_rule(tmp_path):
    book = source.load_book("pride-and-prejudice")
    out = compose.compose(RUN, book, out_dir=tmp_path, log=lambda *_: None)
    L = json.loads((out / "layout.json").read_text())
    facts = {f["id"]: f for f in map(json.loads, open(RUN / "facts.jsonl"))}
    marks = [*L["meetings"], *L["objects"], *[pt for p in L["paths"] for pt in p["points"]]]
    assert marks
    for m in marks:
        assert m["facts"] and all(f in facts for f in m["facts"])
        assert all(facts[f]["passage"] == m["passage"] for f in m["facts"])
    for m in [*L["meetings"], *L["objects"], *L["labels"], *L["roads"]]:
        assert m["rule"] in L["rules"]
    text = json.loads((out / "text.json").read_text())["passages"]
    for p in L["passages"]:
        assert text[p["id"]] == book.text[p["start"]:p["end"]]
        if p["tone"]:
            assert facts[p["tone"]["fact"]]["passage"] == p["id"]
