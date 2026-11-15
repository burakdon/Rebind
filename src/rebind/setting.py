"""Where each passage takes place: the place the characters in the scene physically are.

The reader lists every place a passage mentions, but a mention is not a setting:
Mr. Collins talks about Rosings while sitting at Longbourn, and Darcy's letter
tells of Ramsgate while Elizabeth reads it in Kent. Deciding where a scene is
needs reading, so this pass asks the model once per passage, in order.

  G1 gazetteer  The choices are the book's own named places from verified place facts
                (capitalised, not a possessive, cited at least GAZETTEER_MIN times). A longer
                name that starts with a shorter one is folded into it ("Netherfield Park"
                -> "Netherfield"). (code)
  S1 setting    For each passage the model picks one place from the gazetteer, or
                "elsewhere" / "unclear", says what that rests on, and cites sentences. The
                previous passage's setting is shown, since scenes often continue. (model)
  C1 named      If the model says the place is named, a cited sentence must name it;
                otherwise the basis is downgraded to "implied" and flagged. (code)
  C2 continues  "continues from the previous passage" must match the previous setting;
                otherwise it is downgraded to "implied" and flagged. (code)
  C3 failed     A call that fails or returns nothing usable gives "unclear". (code)

Writes <run>/settings/{gazetteer.json, settings.jsonl, calls.jsonl, run.json}. A stopped
pass resumes where it left off: the prompts depend only on the passages and on settings
already written.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .backends import Backend
from .source import Book, passages
from .verify import mentions

GAZETTEER_MIN = 2
PARAMS = {"temperature": 0.0, "seed": 1342, "max_tokens": 400}
RATIONALE_MAX = 120
BASES = ["named in the passage", "continues from the previous passage", "implied by the passage"]
ELSEWHERE, UNCLEAR = "elsewhere", "unclear"

SYSTEM = """You decide where a passage of a novel physically takes place: the place where the characters in the scene are.
- A place that is only talked about, remembered, planned, or described in a letter is NOT the setting. If Elizabeth reads a letter about Ramsgate while staying in Kent, the setting is where she is.
- Choose the most specific place in the list that fits. Choose "elsewhere" if the scene is at a place not in the list, and "unclear" if the passage does not show where it is (narration, reflection with no scene).
- `basis`: "named in the passage" if a cited sentence names the place; "continues from the previous passage" if the scene simply carries on; otherwise "implied by the passage".
- `evidence`: the numbers of one to three sentences that show it. Keep `rationale` to one short sentence."""

TASK = """Book: {title}
Places: {places}
Previous passage ({prev_id}) was set at: {prev}

PASSAGE {pid} (chapter {chapter}):
<<<
{numbered}
>>>

Where does this passage take place?"""


def gazetteer(facts: list[dict]) -> dict[str, list[str]]:
    """Canonical place -> the names folded into it, most cited first."""
    cited = Counter()
    for f in facts:
        if f["type"] == "place":
            n = " ".join(f["data"]["name"].split())
            if n[:1].isupper() and not n.lower().startswith(("the ", "a ", "an ")) and "’s" not in n and "'s" not in n:
                cited[n] += 1
    canon: dict[str, list[str]] = {}
    for n, _ in sorted(cited.items(), key=lambda kv: (len(kv[0].split()), -kv[1])):
        head = next((c for c in canon if n.startswith(c + " ")), None)
        canon.setdefault(head or n, []).append(n)
    total = {c: sum(cited[a] for a in al) for c, al in canon.items()}
    return {c: canon[c] for c in sorted(canon, key=lambda c: -total[c]) if total[c] >= GAZETTEER_MIN}


def schema(choices: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "setting": {"enum": choices},
            "basis": {"enum": BASES},
            "evidence": {"type": "array", "items": {"type": "integer"}, "maxItems": 3},
            "rationale": {"type": "string", "maxLength": RATIONALE_MAX},
        },
        "required": ["setting", "basis", "evidence", "rationale"],
        "additionalProperties": False,
    }


def check(book: Book, sents, answer: dict, prev: str, gaz: dict[str, list[str]]) -> dict:
    """Apply C1/C2 to a well-formed answer; return the logged decision fields."""
    out = {"setting": answer["setting"], "basis": answer["basis"], "evidence": answer["evidence"],
           "rationale": answer["rationale"], "step": "S1", "flags": []}
    ids = [i for i in answer["evidence"] if 1 <= i <= len(sents)]
    out["spans"] = [[sents[i - 1].start, sents[i - 1].end] for i in ids]
    if answer["basis"] == BASES[0] and answer["setting"] in gaz:
        text = " ".join(book.text[s.start:s.end] for s in (sents[i - 1] for i in ids))
        if not any(mentions(text, alias) for alias in gaz[answer["setting"]]):
            out.update(basis=BASES[2], step="C1")
            out["flags"].append(f"said to be named, but sentences {ids} do not name {answer['setting']!r}")
    if answer["basis"] == BASES[1] and answer["setting"] != prev:
        out.update(basis=BASES[2], step="C2")
        out["flags"].append(f"said to continue the previous passage, which was set at {prev!r}")
    return out


def locate(run_dir: Path, book: Book, backend: Backend, log=print) -> Path:
    run_dir = Path(run_dir)
    out = run_dir / "settings"
    out.mkdir(exist_ok=True)
    facts = [json.loads(l) for l in open(run_dir / "facts.jsonl")]
    gaz = gazetteer(facts)
    choices = list(gaz) + [ELSEWHERE, UNCLEAR]
    sch = schema(choices)
    manifest = json.loads((run_dir / "run.json").read_text())
    by_id = {p.id: p for p in passages(book)}
    plist = [by_id[i] for i in manifest["passages"]]

    meta = {"backend": backend.describe(), "params": PARAMS, "system": SYSTEM, "task": TASK, "schema": sch,
            "gazetteer_min": GAZETTEER_MIN}
    done = {}
    if (out / "settings.jsonl").exists():
        old = json.loads((out / "run.json").read_text()) if (out / "run.json").exists() else {}
        if {k: old.get(k) for k in ("params", "system", "task", "schema")} != {k: meta[k] for k in ("params", "system", "task", "schema")}:
            raise ValueError("settings exist from a different prompt or model; move them aside first")
        done = {r["passage"]: r for r in map(json.loads, open(out / "settings.jsonl"))}
    (out / "gazetteer.json").write_text(json.dumps(gaz, indent=2, ensure_ascii=False))
    (out / "run.json").write_text(json.dumps({**meta, "started": datetime.now(timezone.utc).isoformat()}, indent=2))

    rows = open(out / "settings.jsonl", "a")
    calls = open(out / "calls.jsonl", "a")
    prev, prev_id = UNCLEAR, "none"
    for n, p in enumerate(plist, 1):
        if p.id in done:
            prev, prev_id = done[p.id]["setting"], p.id
            continue
        numbered, sents = p.numbered_text(book)
        task = TASK.format(title=book.title, places=", ".join(choices), prev_id=prev_id, prev=prev, pid=p.id,
                           chapter=p.chapter, numbered=numbered)
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
        cid = f"S1/{p.id}"
        try:
            resp = backend.chat(messages, sch, schema_name="setting", **PARAMS)
        except Exception as e:
            resp = {"text": "", "error": repr(e)}
        calls.write(json.dumps({"id": cid, "messages": messages, **resp}, ensure_ascii=False) + "\n")
        calls.flush()
        try:
            ans = json.loads(resp.get("text") or "")
            assert ans["setting"] in choices and ans["basis"] in BASES
            row = check(book, sents, ans, prev, gaz)
        except (json.JSONDecodeError, AssertionError, KeyError, TypeError):
            row = {"setting": UNCLEAR, "basis": None, "evidence": [], "spans": [], "rationale": "",
                   "step": "C3", "flags": ["the call failed or gave no usable answer"]}
        row = {"passage": p.id, "chapter": p.chapter, **row, "call": cid}
        rows.write(json.dumps(row, ensure_ascii=False) + "\n")
        rows.flush()
        prev, prev_id = row["setting"], p.id
        log(f"[{n}/{len(plist)}] {p.id}: {row['setting']} ({row['basis']}){' FLAG' if row['flags'] else ''} "
            f"{resp.get('latency_s', 0):.0f}s")
    rows.close()
    calls.close()
    settled = [json.loads(l) for l in open(out / "settings.jsonl")]
    meta.update(finished=datetime.now(timezone.utc).isoformat(),
                counts={"by_setting": dict(Counter(r["setting"] for r in settled).most_common()),
                        "by_basis": dict(Counter(r["basis"] for r in settled)),
                        "flagged": sum(bool(r["flags"]) for r in settled)})
    (out / "run.json").write_text(json.dumps(meta, indent=2))
    return out
