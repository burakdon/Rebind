"""The setting pass: the gazetteer comes from the facts, and code checks the model's claims."""

import re

from rebind import setting, source


def place(name):
    return {"type": "place", "data": {"name": name, "kind": "estate"}}


def test_gazetteer_folds_longer_names_and_drops_rare_or_possessive_ones():
    facts = [place("Netherfield"), place("Netherfield Park"), place("Rosings"), place("Rosings"),
             place("Mr. Collins's garden"), place("Mr. Collins's garden"), place("the house"), place("the house"),
             place("Epsom")]
    assert setting.gazetteer(facts) == {"Netherfield": ["Netherfield", "Netherfield Park"], "Rosings": ["Rosings"]}


def _first_passage():
    book = source.load_book("pride-and-prejudice")
    p = source.passages(book)[0]
    return book, p.numbered_text(book)[1]


def test_a_place_said_to_be_named_must_be_named():
    book, sents = _first_passage()
    gaz = {"Netherfield": ["Netherfield", "Netherfield Park"], "Pemberley": ["Pemberley"]}
    k = next(i for i, s in enumerate(sents, 1) if re.search(r"Netherfield", book.text[s.start:s.end]))
    ok = setting.check(book, sents, {"setting": "Netherfield", "basis": setting.BASES[0], "evidence": [k],
                                     "rationale": "r"}, "unclear", gaz)
    assert ok["step"] == "S1" and not ok["flags"]
    bad = setting.check(book, sents, {"setting": "Pemberley", "basis": setting.BASES[0], "evidence": [k],
                                      "rationale": "r"}, "unclear", gaz)
    assert bad["step"] == "C1" and bad["basis"] == setting.BASES[2] and bad["flags"]


def test_continuing_must_match_the_previous_setting():
    book, sents = _first_passage()
    ans = {"setting": "Pemberley", "basis": setting.BASES[1], "evidence": [1], "rationale": "r"}
    assert setting.check(book, sents, ans, "Pemberley", {"Pemberley": ["Pemberley"]})["step"] == "S1"
    assert setting.check(book, sents, ans, "Longbourn", {"Pemberley": ["Pemberley"]})["step"] == "C2"
