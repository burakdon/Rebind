"""Sentence labels: the model must label every sentence once, and the checks must count honestly."""

import json

import pytest

from rebind import checks, labels


@pytest.mark.parametrize("reading", ["a", "b"])
def test_the_schema_has_one_slot_per_sentence_and_parses_back(reading):
    spec = labels.READINGS[reading]
    sch = labels.schema(3, spec)
    assert sch["required"] == ["1", "2", "3"] and sch["additionalProperties"] is False
    options = sch["properties"]["1"]["enum"]
    assert len(options) == 6 and len(set(options)) == 6
    answer = {"1": options[0], "2": options[3], "3": options[5]}
    feeling, pace = labels.parse(json.dumps(answer), 3)
    for got_f, got_p, said in zip(feeling, pace, answer.values()):
        assert {got_f, got_p} == set(said.split())
    with pytest.raises(KeyError):
        labels.parse(json.dumps({"1": options[0]}), 2)


def test_the_two_readings_ask_in_opposite_orders():
    a, b = labels.READINGS["a"], labels.READINGS["b"]
    assert a["order"] == b["order"][::-1] and a["feelings"] == b["feelings"][::-1] and a["paces"] == b["paces"][::-1]
    assert a["system"] != b["system"]


def test_names_are_swapped_as_whole_words():
    table = {"Darcy": "Barlow", "Elizabeth": "Agnes", "Eliza": "Clara"}
    assert labels.swap("Mr. Darcy saw Elizabeth; Eliza laughed at Darcy's pride.", table) == \
        "Mr. Barlow saw Agnes; Clara laughed at Barlow's pride."
    assert labels.swap("Elizabethan", table) == "Elizabethan"


def test_agreement_and_kappa():
    assert checks.agreement([]) is None
    perfect = checks.agreement([(0, 0), (1, 1), (2, 2), (1, 1)])
    assert perfect["same"] == 1 and perfect["kappa"] == 1
    # Both say 0 nine times in ten but never agree on the 1s: high agreement, no skill.
    chance = checks.agreement([(0, 0)] * 8 + [(0, 1), (1, 0)])
    assert chance["same"] == 0.8 and chance["kappa"] < 0
