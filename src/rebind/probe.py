"""How firmly does a label hold? Take one passage, remove one word at a time, and ask again.

This is the simplest relative of LIME (Ribeiro et al., 2016): the input is changed a little and the answer
watched. No model is fitted to the changes; each word is simply left out once. The question, the answer
format and the decoding (temperature 0, a fixed seed) are exactly those of `rebind label --reading a`, so
with nothing removed the model gives the labels the scarf was knitted from, and gives them again if asked again.

It measures how fragile a label is, not why the model gave it. It also costs one call per word, about a
quarter of an hour for one passage on a laptop, so it is run on single passages and not on a book.

Results are kept with the run, in probes/<passage>.jsonl, one line per call, and a summary of every probed
passage of the book is written to site/data/<book>/probes.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import labels
from .backends import Backend
from .source import ROOT, Book, _unwrap, passages

CLOSERS = ".!?;:,\"'”’"


def without(sentence: str, j: int) -> str:
    """The sentence with its j-th word left out. If that was the last word, its closing mark is kept."""
    words = sentence.split(" ")
    rest = words[:j] + words[j + 1:]
    tail = "".join(c for c in words[j][-2:] if c in CLOSERS) if j == len(words) - 1 else ""
    if tail and rest:
        rest[-1] = rest[-1].rstrip(",;:") + tail
    return " ".join(rest)


def probe(run_dir: Path, book: Book, backend: Backend, passage_id: str, log=print) -> Path:
    """Ask once with nothing removed, once more to see the answer repeat, then once for every word."""
    p = next(q for q in passages(book) if q.id == passage_id)
    paras = [[_unwrap(book.text[s.start:s.end]) for s in sents] for sents in p.sentences(book)]
    flat = [s for para in paras for s in para]
    n, spec = len(flat), labels.READINGS["a"]

    def ask(sents: list[str]) -> tuple[list[str], list[str]]:
        parts, k = [], 0
        for para in paras:
            parts.append(" ".join(f"[{k + j + 1}] {sents[k + j]}" for j in range(len(para))))
            k += len(para)
        messages = [{"role": "system", "content": spec["system"]},
                    {"role": "user", "content": spec["task"].format(numbered="\n\n".join(parts), n=n)}]
        resp = backend.chat(messages, labels.schema(n, spec), schema_name="labels", max_tokens=80 + 14 * n, **labels.PARAMS)
        return labels.parse(resp["text"], n)

    out = Path(run_dir) / "probes" / f"{passage_id}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {(r["sentence"], r["word"]) for r in map(json.loads, open(out))} if out.exists() else set()
    f = open(out, "a")

    def record(i: int, j: int, word: str | None, sents: list[str]) -> None:
        feeling, pace = ask(sents)
        f.write(json.dumps({"sentence": i, "word": j, "removed": word, "feeling": feeling, "pace": pace},
                           ensure_ascii=False) + "\n")
        f.flush()
        done.add((i, j))

    for rep in (-1, -2):                 # sentence 0: nothing removed, asked twice
        if (0, rep) not in done:
            record(0, rep, None, flat)
    total, k = sum(len(s.split(" ")) for s in flat), 0
    for i, s in enumerate(flat, 1):
        for j, word in enumerate(s.split(" ")):
            k += 1
            if (i, j) in done:
                continue
            try:
                record(i, j, word, flat[:i - 1] + [without(s, j)] + flat[i:])
                log(f"[{k}/{total}] sentence {i} without {word!r}")
            except Exception as e:       # a failed call is left out and can be retried by running again
                log(f"[{k}/{total}] sentence {i} without {word!r}: FAILED {e!r}")
    f.close()
    return out


def summary(path: Path) -> dict:
    """What one passage's probe found: for each sentence, the words whose removal changes its own label."""
    rows = [json.loads(line) for line in open(path)]
    base = next(r for r in rows if r["sentence"] == 0 and r["word"] == -1)
    again = next((r for r in rows if r["sentence"] == 0 and r["word"] == -2), None)
    n, tests = len(base["feeling"]), [r for r in rows if r["sentence"] > 0]
    both = lambda r, q: (r["feeling"][q], r["pace"][q])  # noqa: E731
    sentences = []
    for i in range(1, n + 1):
        mine = [r for r in tests if r["sentence"] == i]
        sentences.append({"n": i, "feeling": base["feeling"][i - 1], "pace": base["pace"][i - 1], "words": len(mine),
                          "flips": [{"word": r["removed"].strip(CLOSERS + "“‘("), "feeling": r["feeling"][i - 1],
                                     "pace": r["pace"][i - 1]} for r in mine if both(r, i - 1) != both(base, i - 1)]})
    return {"words": len(tests), "repeats": bool(again) and both(again, slice(None)) == both(base, slice(None)),
            "holds": sum(not s["flips"] for s in sentences), "sentences": sentences,
            # removing a word from one sentence should leave the others alone; this counts when it did not
            "spill": {"changes": sum(both(r, q) != both(base, q) for r in tests for q in range(n) if q != r["sentence"] - 1),
                      "chances": len(tests) * (n - 1)}}


def publish(run_dir: Path, slug: str, model: str, out_dir: Path | None = None) -> Path:
    """probes.json for the site: every passage of this run that has been probed."""
    doc = {"model": model, "method": "Each word of the passage is left out once and the question of the first reading asked again.",
           "passages": {f.stem: summary(f) for f in sorted((Path(run_dir) / "probes").glob("*.jsonl"))}}
    out = Path(out_dir or ROOT / "site" / "data" / slug) / "probes.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    return out
