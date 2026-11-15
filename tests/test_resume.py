"""A run stopped part-way and resumed must end up exactly like one that never stopped."""

import json
import re

import pytest

from rebind import extract, source


class FakeReader:
    """Deterministic stand-in for a model: names whoever is called "Mr./Mrs. X" in sentence [1]."""

    spec = "fake:reader"
    model = "reader"

    def __init__(self, fail_at: int | None = None):
        self.fail_at, self.n = fail_at, 0

    def describe(self):
        return {"spec": self.spec, "model": self.model, "digest": "fake"}

    def chat(self, messages, schema, *, schema_name, **_):
        self.n += 1
        if self.n == self.fail_at:
            raise TimeoutError("machine went to sleep")
        text = messages[1]["content"]
        first = re.search(r"\[1\] ([^\[]*)", text).group(1)
        names = sorted(set(re.findall(r"\bMrs?\. [A-Z][a-z]+", first)))
        out = {
            "characters": {"characters": [{"name": n, "called_here": n, "evidence": [1]} for n in names]
                           or [{"name": "Nobody", "called_here": "nobody", "evidence": [1]}]},
            "interactions": {"interactions": []},
            "setting": {"places": [], "objects": []},
            "events": {"events": [{"summary": "Something happens.", "evidence": [1]}],
                       "tone": {"tension": 3, "warmth": 5, "reason": "r", "evidence": [1]}},
            "repairs": {"fixes": []},
        }[schema_name]
        return {"text": json.dumps(out), "finish_reason": "stop", "latency_s": 0.0}


def strip_run_id(rows):
    """Call ids carry the run id; everything else must match exactly."""
    out = []
    for r in rows:
        r = {k: v for k, v in r.items() if k not in ("at", "latency_s")}
        for k in ("id", "call"):
            if isinstance(r.get(k), str) and "/" in r[k]:
                r[k] = r[k].split("/", 1)[1]
        out.append(r)
    return out


def read_all(run):
    return {name: strip_run_id([json.loads(l) for l in open(run / name)])
            for name in ("calls.jsonl", "facts.jsonl", "rejected.jsonl", "progress.jsonl")}


@pytest.fixture(scope="module")
def book():
    return source.load_book("pride-and-prejudice")


def test_resume_matches_uninterrupted_run(book, tmp_path):
    ps = source.passages(book)[:4]
    quiet = lambda *_: None
    clean = extract.run(book, ps, FakeReader(), out_root=tmp_path / "clean", log=quiet)

    # Fail on the 6th call, i.e. inside the second passage; the run carries on past it.
    broken = extract.run(book, ps, FakeReader(fail_at=6), out_root=tmp_path / "broken", log=quiet)
    progress = [json.loads(l) for l in open(broken / "progress.jsonl")]
    assert [r["call_errors"] > 0 for r in progress] == [False, True, False, False]

    resumed = extract.run(book, ps, FakeReader(), log=quiet, resume=broken)
    manifest = json.loads((resumed / "run.json").read_text())
    assert manifest["resumed"][0]["passages_done"] == 1  # only the clean prefix is kept

    assert read_all(resumed) == read_all(clean)
    assert manifest["counts"] == json.loads((clean / "run.json").read_text())["counts"]


def test_resume_refuses_a_different_model(book, tmp_path):
    ps = source.passages(book)[:1]
    run = extract.run(book, ps, FakeReader(), out_root=tmp_path, log=lambda *_: None)
    other = FakeReader()
    other.model = "another-reader"
    with pytest.raises(ValueError, match="model"):
        extract.run(book, ps, other, log=lambda *_: None, resume=run)
