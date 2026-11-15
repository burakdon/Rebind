"""The merge pass: what code decides, and what it refuses to let the model decide."""

import json

from rebind import entities as E


def fact(name, called, chapter=1, text="placeholder"):
    return {"type": "character", "chapter": chapter, "passage": f"c{chapter:02d}.p01",
            "data": {"name": name, "called_here": called}, "evidence": {"source_text": text}}


class ScriptedModel:
    """Answers the anchor call and every tail call from a fixed script of same_as links."""

    spec, model = "fake:resolver", "resolver"

    def __init__(self, links: dict[str, tuple[str, str, str]], omit=()):
        self.links, self.omit = links, set(omit)  # name -> (same_as, kind, basis)

    def describe(self):
        return {"spec": self.spec}

    def chat(self, messages, schema, *, schema_name, **_):
        out = {}
        for name in schema["required"]:
            if name in self.omit:
                continue
            same_as, kind, basis = self.links.get(name, (name, "person", "no merge"))
            if same_as not in schema["properties"][name]["properties"]["same_as"]["enum"]:
                same_as = "new_person"
            out[name] = {"same_as": same_as, "kind": kind, "basis": basis, "rationale": "scripted"}
        return {"text": json.dumps(out), "finish_reason": "stop"}


def make_run(tmp_path, counts):
    run = tmp_path / "run"
    run.mkdir()
    with open(run / "facts.jsonl", "w") as f:
        for name, n in counts.items():
            for i in range(n):
                f.write(json.dumps(fact(name, name.split()[-1], chapter=1 + i % 3, text=f"... {name} ...")) + "\n")
    return run


def table(run):
    return {t["canonical"]: t for t in json.loads((run / "entities" / "entities.json").read_text())}


def decisions(run):
    return {d["name"]: d for d in map(json.loads, open(run / "entities" / "decisions.jsonl"))}


def test_spelling_variants_are_one_name_before_any_model_sees_them():
    names = E.gather([fact("Mr. Darcy", "Darcy"), fact("mr.  darcy", "Darcy"), fact("Miss De Bourgh", "x"),
                      fact("Miss de Bourgh", "x")])
    assert len(names) == 2
    assert names[E.key("Mr. Darcy")]["spellings"] == {"Mr. Darcy": 1, "mr.  darcy": 1}


def test_examples_prefer_a_real_name_over_a_pronoun():
    names = E.gather([fact("Jane Bennet", "she", text="she smiled"), fact("Jane Bennet", "Jane", text="Jane smiled")])
    assert names[E.key("Jane Bennet")]["examples"] == ['ch.1 as "Jane": Jane smiled']


def test_links_form_entities_and_tail_attaches(tmp_path):
    run = make_run(tmp_path, {"Elizabeth Bennet": 9, "Lizzy": 6, "Mr. Darcy": 8, "Pemberley": 5, "Eliza": 1})
    model = ScriptedModel({
        "Lizzy": ("Elizabeth Bennet", "person", "nickname or first name"),
        "Pemberley": ("Pemberley", "not_a_person", "no merge"),
        "Eliza": ("elizabeth-bennet", "person", "nickname or first name"),
    })
    E.resolve(run, model, log=lambda *_: None)
    t = table(run)
    assert t["Elizabeth Bennet"]["names"] == ["Elizabeth Bennet", "Lizzy", "Eliza"]
    assert t["Elizabeth Bennet"]["mentions"] == 16
    assert t["Pemberley"]["kind"] == "not_a_person"
    d = decisions(run)
    assert (d["Lizzy"]["step"], d["Eliza"]["step"]) == ("M1", "M2")
    assert E.load(run)[E.key("lizzy")]["id"] == "elizabeth-bennet"


def test_titles_of_both_sexes_are_split_apart(tmp_path):
    run = make_run(tmp_path, {"Mrs. Bennet": 9, "Mr. Bennet": 6})
    E.resolve(run, ScriptedModel({"Mr. Bennet": ("Mrs. Bennet", "person", "title or surname form")}),
              log=lambda *_: None)
    assert set(table(run)) == {"Mrs. Bennet", "Mr. Bennet"}
    d = decisions(run)["Mr. Bennet"]
    assert d["step"] == "R2" and d["overrode"]["entity"] == "mrs-bennet"


def test_names_the_model_skips_keep_their_own_entity(tmp_path):
    run = make_run(tmp_path, {"Jane Bennet": 7, "Mr. Bingley": 6})
    E.resolve(run, ScriptedModel({}, omit={"Mr. Bingley"}), log=lambda *_: None)
    assert decisions(run)["Mr. Bingley"]["step"] == "R3"
    assert "Mr. Bingley" in table(run)


def test_merges_resting_on_outside_knowledge_are_flagged(tmp_path):
    run = make_run(tmp_path, {"Charlotte Lucas": 60, "Mrs. Collins": 55})
    E.resolve(run, ScriptedModel({"Mrs. Collins": ("Charlotte Lucas", "person", "knowledge of the novel")}),
              log=lambda *_: None)
    flags = decisions(run)["Mrs. Collins"]["flags"]
    assert any("knowledge of the novel" in f for f in flags)
    assert any("several major names" in f for f in flags)


def test_references_are_never_merged_into_a_person(tmp_path):
    run = make_run(tmp_path, {"Mr. Darcy": 9, "the late Mr. Darcy": 2, "Mr. Wickham's father": 1, "her sister": 6,
                              "the officers": 5})
    model = ScriptedModel({n: ("mr-darcy", "person", "knowledge of the novel")
                           for n in ["the late Mr. Darcy", "Mr. Wickham's father", "her sister"]})
    E.resolve(run, model, log=lambda *_: None)
    t = table(run)
    assert t["Mr. Darcy"]["names"] == ["Mr. Darcy"]
    assert (t["her sister"]["kind"], t["the officers"]["kind"]) == ("reference", "group")
    assert decisions(run)["the late Mr. Darcy"]["step"] == "R4"


def test_different_given_names_are_split_but_nicknames_are_not(tmp_path):
    run = make_run(tmp_path, {"Miss Darcy": 9, "Georgiana Darcy": 5, "Anne Darcy": 2, "Anne": 1,
                              "Kitty Bennet": 6, "Catherine Bennet": 5})
    model = ScriptedModel({
        "Georgiana Darcy": ("Miss Darcy", "person", "relation shown in the examples"),
        "Anne Darcy": ("miss-darcy", "person", "knowledge of the novel"),
        "Anne": ("miss-darcy", "person", "knowledge of the novel"),
        "Catherine Bennet": ("Kitty Bennet", "person", "nickname or first name"),
    })
    E.resolve(run, model, log=lambda *_: None)
    t = {tuple(v["names"]) for v in table(run).values()}
    assert ("Miss Darcy", "Georgiana Darcy") in t or ("Georgiana Darcy", "Miss Darcy") in t
    assert ("Anne Darcy", "Anne") in t  # split off together, as one person
    assert ("Kitty Bennet", "Catherine Bennet") in t
    assert decisions(run)["Anne"]["step"] == "R5"


def test_miss_and_mrs_of_one_surname_are_two_women(tmp_path):
    run = make_run(tmp_path, {"Miss Bingley": 9, "Mrs. Bingley": 3})
    E.resolve(run, ScriptedModel({"Mrs. Bingley": ("miss-bingley", "person", "knowledge of the novel")}),
              log=lambda *_: None)
    assert set(table(run)) == {"Miss Bingley", "Mrs. Bingley"}
    assert decisions(run)["Mrs. Bingley"]["step"] == "R6"


def test_one_person_cannot_carry_two_maiden_surnames(tmp_path):
    # The model really did this, claiming Lady Catherine's "full name is Georgiana Darcy".
    run = make_run(tmp_path, {"Miss Darcy": 9, "Georgiana Darcy": 5, "Miss de Bourgh": 6})
    E.resolve(run, ScriptedModel({
        "Georgiana Darcy": ("Miss Darcy", "person", "relation shown in the examples"),
        "Miss de Bourgh": ("Miss Darcy", "person", "knowledge of the novel"),
    }), log=lambda *_: None)
    t = {tuple(sorted(v["names"])) for v in table(run).values()}
    assert t == {("Georgiana Darcy", "Miss Darcy"), ("Miss de Bourgh",)}
    assert decisions(run)["Miss de Bourgh"]["step"] == "R7"


def test_married_names_are_not_split_off(tmp_path):
    run = make_run(tmp_path, {"Lydia Bennet": 9, "Mrs. Wickham": 5})
    E.resolve(run, ScriptedModel({"Mrs. Wickham": ("Lydia Bennet", "person", "married name")}), log=lambda *_: None)
    assert table(run)["Lydia Bennet"]["names"] == ["Lydia Bennet", "Mrs. Wickham"]


def test_same_given_name_and_surname_are_merged_by_code(tmp_path):
    run = make_run(tmp_path, {"Kitty Bennet": 9, "Catherine Bennet": 6, "Lady Catherine de Bourgh": 7})
    E.resolve(run, ScriptedModel({}), log=lambda *_: None)
    t = table(run)
    assert t["Kitty Bennet"]["names"] == ["Kitty Bennet", "Catherine Bennet"]
    assert t["Lady Catherine de Bourgh"]["names"] == ["Lady Catherine de Bourgh"]
    assert decisions(run)["Catherine Bennet"]["step"] == "R8"


def test_nothing_is_attached_to_a_reference(tmp_path):
    # The model really put Mrs. Reynolds, Mrs. Hill and Mrs. Jenkinson under "the housekeeper".
    run = make_run(tmp_path, {"Elizabeth Bennet": 9, "the housekeeper": 6, "Mrs. Reynolds": 2, "Mrs. Hill": 1})
    model = ScriptedModel({n: ("the-housekeeper", "person", "relation shown in the examples")
                           for n in ["Mrs. Reynolds", "Mrs. Hill"]})
    E.resolve(run, model, log=lambda *_: None)
    t = table(run)
    assert t["the housekeeper"]["names"] == ["the housekeeper"]
    assert {"Mrs. Reynolds", "Mrs. Hill"} <= set(t)


def test_nothing_is_attached_to_a_plural_reference(tmp_path):
    run = make_run(tmp_path, {"Elizabeth Bennet": 9, "the elder ones": 6, "Forsters": 1})
    E.resolve(run, ScriptedModel({"Forsters": ("the-elder-ones", "group", "knowledge of the novel")}),
              log=lambda *_: None)
    assert table(run)["the elder ones"]["names"] == ["the elder ones"]
