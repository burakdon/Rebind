"""Re-applying a stricter checker to a saved run moves facts out without losing them."""

import json
import re

from rebind import extract, source


def test_recheck_moves_pronoun_facts_and_keeps_the_old_file(tmp_path):
    book = source.load_book("pride-and-prejudice")
    p = source.passages(book)[0]
    _, sents = p.numbered_text(book)
    i = 1  # the pronoun rule refuses before looking at the sentence
    run = tmp_path / "run"
    run.mkdir()
    good = extract.check(book, p, sents, "character", {"name": "Mr. Bennet", "called_here": "Mr. Bennet"},
                         [next(k for k, s in enumerate(sents, 1) if re.search(r"Mr\.\s+Bennet", book.text[s.start:s.end]))], "c")
    # What checker 1 accepted: the word "her" occurs in the sentence.
    old = {**extract.check(book, p, sents, "character", {"name": "Mrs. Bennet", "called_here": "Mrs. Bennet"},
                           [i], "c"), "data": {"name": "Mrs. Bennet", "called_here": "her"}, "status": "verified"}
    assert good["status"] == "verified"
    (run / "facts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in (good, old)))
    (run / "rejected.jsonl").write_text("")
    (run / "run.json").write_text(json.dumps({"book": {"sha256": book.sha256},
                                              "counts": {"character_verified": 2}}))

    summary = extract.recheck(run, book, log=lambda *_: None)
    assert summary["moved"] == 1 and summary["by_support"] == {"pronoun only": 1}
    assert [json.loads(l)["data"]["called_here"] for l in open(run / "facts.jsonl")] == ["Mr. Bennet"]
    moved = [json.loads(l) for l in open(run / "rejected.jsonl")]
    assert moved[0]["recheck"]["was"] == "verified" and moved[0]["id"] == old["id"]
    assert len((run / "facts.checker-1.jsonl").read_text().splitlines()) == 2
    m = json.loads((run / "run.json").read_text())
    assert m["checker"] == extract.CHECKER and m["counts"]["character_verified"] == 1
    assert extract.recheck(run, book, log=lambda *_: None)["moved"] == 0  # running it again is a no-op
