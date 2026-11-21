"""Read a book passage by passage and write an auditable ledger of facts.

A run directory holds:
  run.json        what was run: book hash, model, prompts, schemas, parameters, counts
  calls.jsonl     every model call, verbatim: messages in, raw text out, timing
  facts.jsonl     accepted facts, each with its cited sentences resolved to file offsets
  rejected.jsonl  everything the checker refused, with the reason

Each passage is read in four focused calls (characters; interactions; places
and objects; events and tone), because small models given one large schema
tend to leave most of it empty. The passage is shown with numbered sentences
and every item cites sentence numbers, so evidence always resolves to exact
spans of the source file and a model cannot invent a quotation.

A fact is accepted only if its sentence numbers exist in the passage and, for
characters, places and objects, the cited sentences actually name the thing
(a character "named" only by a pronoun is refused: code cannot check who "her" is).
Items that fail get one repair round in which the model is told why and may
cite again or withdraw. Both attempts stay in the ledger.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .backends import Backend
from .schema import CharactersOut, EventsOut, InteractionsOut, Repairs, SettingOut, inline_schema
from .source import ROOT, Book, Passage, Span, passages
from .verify import mentions, only_referring_words, says

SYSTEM = """You are a careful literary annotator. You read ONE passage from a novel and record what is in it.

Rules:
- Record only what this passage itself shows. Do not use outside knowledge of the novel.
- The passage's sentences are numbered [1], [2], ... Every item needs "evidence": the numbers of the one to three sentences that show it. If no sentence shows it, leave the item out.
- Use full canonical names for people (e.g. "Elizabeth Bennet", not "Lizzy"). If someone is in the known-characters list, use that exact name."""


@dataclass
class Task:
    key: str
    model: type[BaseModel]
    instruction: str
    fields: dict[str, str]  # output field -> fact type; "tone" is a single object


TASKS = [
    Task("characters", CharactersOut,
         "List every character who appears in or is referred to by this passage. For each, give "
         "`called_here`, the words this passage uses for them (e.g. 'his lady', 'Lizzy', 'Mr. Bingley'), "
         "and cite sentences that contain those words.",
         {"characters": "character"}),
    Task("interactions", InteractionsOut,
         "List each interaction in which two or more of these characters deal with each other directly "
         "in this passage (talk, meet, dance, write, quarrel, visit, propose): {cast_here}. "
         "Give an empty list if there is none.",
         {"interactions": "interaction"}),
    Task("setting", SettingOut,
         "List the places where this passage happens or that matter in it, and the physical objects that "
         "matter (a letter, a carriage, a hat, a pianoforte), each with how the passage describes it. "
         "Cited sentences must name the place or object. Empty lists are fine.",
         {"places": "place", "objects": "object"}),
    Task("events", EventsOut,
         "List what happens in this passage, one sentence per event, in order (one to five events). "
         "Then rate the passage's tension and warmth from 0 to 10 with a one-sentence reason.",
         {"events": "event", "tone": "tone"}),
]

REPAIR = """Some of your evidence could not be accepted:

{items}

For each numbered item, give the sentence numbers that show it (for characters, places and objects the sentences must contain the name), or [] to withdraw the item."""

PARAMS = {"temperature": 0.0, "seed": 1342, "max_tokens": 2000}
# Bumped whenever check() changes what it accepts; `rebind recheck` brings old runs up to date.
#   1  called_here found anywhere in the cited text
#   2  whole words only, and a called_here made only of pronouns is refused
CHECKER = 2
NAMED_KINDS = {"character", "place", "object"}


def prompt_version() -> str:
    blob = json.dumps(
        [SYSTEM, REPAIR, [(t.key, t.instruction, inline_schema(t.model)) for t in TASKS], inline_schema(Repairs)],
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def user_message(book: Book, p: Passage, numbered: str, cast: list[str], task: str) -> str:
    known = ", ".join(cast) if cast else "(none yet)"
    return (
        f"Book: {book.title} by {book.author}\n"
        f"Passage {p.id} (chapter {p.chapter})\n"
        f"Known characters so far: {known}\n\n"
        f"PASSAGE:\n<<<\n{numbered}\n>>>\n\n"
        f"TASK: {task}"
    )


def fact_id(passage_id: str, kind: str, data: dict) -> str:
    h = hashlib.sha1(json.dumps([passage_id, kind, data], sort_keys=True).encode()).hexdigest()
    return f"f-{h[:10]}"


def check(book: Book, p: Passage, sents: list[Span], kind: str, data: dict, cited: list[int], call_id: str) -> dict:
    rec = {
        "id": fact_id(p.id, kind, data),
        "type": kind,
        "passage": p.id,
        "chapter": p.chapter,
        "data": data,
        "evidence": {"sentences": cited},
        "call": call_id,
    }
    ids = sorted(set(cited or []))
    bad = [i for i in ids if not 1 <= i <= len(sents)]
    if not ids or bad:
        rec.update(status="rejected", reason=f"no such sentence {bad}" if bad else "no evidence cited")
        return rec
    spans = [sents[i - 1] for i in ids]
    text = " ".join(book.text[s.start:s.end] for s in spans)
    rec["evidence"]["spans"] = [[s.start, s.end] for s in spans]
    rec["evidence"]["source_text"] = " … ".join(book.text[s.start:s.end] for s in spans)
    if kind == "character":
        # Exact words only: a shared surname ("Elizabeth Bennet") must not count
        # as evidence for another family member ("Mrs. Bennet").
        # A pronoun ("her", "you") is in nearly every sentence, so finding it proves nothing.
        if only_referring_words(data["called_here"]):
            rec.update(status="rejected", support="pronoun only",
                       reason=f"{data['called_here']!r} is only a pronoun, so code cannot check who it is; "
                              f"cite a sentence that names them")
            return rec
        named = says(text, data["called_here"])
    elif kind in NAMED_KINDS:
        named = mentions(text, data["name"])
    else:
        named = None
    rec["support"] = "names it" if named else ("unchecked" if named is None else "does not name it")
    if named is False:
        rec.update(status="rejected",
                   reason=f"sentence {ids} does not name {data.get('called_here') or data['name']!r}")
        return rec
    rec["status"] = "verified"
    return rec


def label(r: dict) -> str:
    d = r["data"]
    return f"{r['type']} {d.get('name') or d.get('summary') or d.get('reason')!r}"


def slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "-", s).strip("-")


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in open(path)] if path.exists() else []


def _resume_state(out: Path, manifest: dict, book: Book, backend: Backend, plist: list[Passage]):
    """Reload a stopped run. Records of a passage that was cut off part-way are dropped
    so it is read again from the start; the cast is rebuilt in the original order, so a
    resumed run sends the model exactly the prompts an uninterrupted one would have."""
    same = {
        "book": manifest["book"]["sha256"] == book.sha256,
        "prompt": manifest["prompt_version"] == prompt_version(),
        "model": manifest["backend"]["model"] == backend.model,
        "digest": manifest["backend"].get("digest") == backend.describe().get("digest"),
        "passages": manifest["passages"] == [p.id for p in plist],
        "params": manifest["params"] == PARAMS,
        "checker": manifest.get("checker", 1) == CHECKER,
    }
    if not all(same.values()):
        raise ValueError(f"cannot resume {out.name}: these differ from the original run: "
                         f"{[k for k, v in same.items() if not v]}")
    # Keep the longest run of cleanly read passages from the start; a passage with a
    # failed call (a timeout across a sleep, say) and everything after it is read again.
    progress = []
    for want, r in zip(manifest["passages"], _jsonl(out / "progress.jsonl")):
        if r["passage"] != want or r["call_errors"]:
            break
        progress.append(r)
    done = {r["passage"] for r in progress}
    (out / "progress.jsonl").write_text("".join(json.dumps(r) + "\n" for r in progress))
    for name in ("calls.jsonl", "facts.jsonl", "rejected.jsonl"):
        kept = [r for r in _jsonl(out / name) if r.get("passage") in done]
        (out / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept))
    cast: Counter[str] = Counter()
    for r in _jsonl(out / "facts.jsonl"):
        if r["type"] == "character":
            cast[r["data"]["name"]] += 1
    counts: Counter[str] = Counter()
    for r in progress:
        counts.update(r["counts"])
    return done, cast, counts


def run(book: Book, plist: list[Passage], backend: Backend, out_root: Path | None = None, log=print,
        resume: Path | None = None, only: list[str] | None = None) -> Path:
    """`only` asks just the named tasks (e.g. ["characters"], which is all the scarf needs). The run records
    which tasks it asked, and a resumed run asks the same ones."""
    started = datetime.now(timezone.utc)
    unknown = set(only or []) - {t.key for t in TASKS}
    if unknown:
        raise ValueError(f"no such task: {sorted(unknown)}; choose from {[t.key for t in TASKS]}")
    tasks = [t for t in TASKS if not only or t.key in only]
    repair_schema = inline_schema(Repairs)
    if resume:
        out = Path(resume)
        manifest = json.loads((out / "run.json").read_text())
        run_id = manifest["run_id"]
        done, cast, counts = _resume_state(out, manifest, book, backend, plist)
        asked = {t["key"] for t in manifest["tasks"]}
        tasks = [t for t in TASKS if t.key in asked]
        manifest.setdefault("resumed", []).append({"at": started.isoformat(), "passages_done": len(done)})
        log(f"resuming {run_id}: {len(done)} of {len(plist)} passages already read")
    else:
        run_id = f"{started:%Y%m%dT%H%M%SZ}-{slugify(backend.model)}"
        out = (out_root or ROOT / "out" / book.slug / "runs") / run_id
        out.mkdir(parents=True, exist_ok=True)
        manifest = {
            "run_id": run_id,
            "book": {"slug": book.slug, "sha256": book.sha256, "file": str(book.path.relative_to(ROOT))},
            "backend": backend.describe(),
            "prompt_version": prompt_version(),
            "system_prompt": SYSTEM,
            "tasks": [{"key": t.key, "instruction": t.instruction, "schema": inline_schema(t.model)} for t in tasks],
            "repair_prompt": REPAIR,
            "params": PARAMS,
            "checker": CHECKER,
            "passages": [p.id for p in plist],
            "started": started.isoformat(),
        }
        done, cast, counts = set(), Counter(), Counter()
    (out / "run.json").write_text(json.dumps(manifest, indent=2))

    mode = "a" if resume else "w"
    with open(out / "calls.jsonl", mode) as calls, open(out / "facts.jsonl", mode) as facts, open(
        out / "rejected.jsonl", mode
    ) as rejected, open(out / "progress.jsonl", mode) as progress:

        def call(call_id, passage_id, messages, sch, name):
            try:
                resp = backend.chat(messages, sch, schema_name=name, **PARAMS)
            except Exception as e:  # network, server or decoding failure: log and move on
                resp = {"text": "", "error": repr(e)}
            calls.write(json.dumps({"id": call_id, "passage": passage_id, "messages": messages, **resp},
                                   ensure_ascii=False) + "\n")
            calls.flush()
            return resp

        for n, p in enumerate(plist, 1):
            if p.id in done:
                continue
            pc: Counter[str] = Counter()
            errors = 0
            numbered, sents = p.numbered_text(book)
            known = [name for name, _ in cast.most_common(30)]
            cast_here: list[str] = []
            ok = total = repaired = 0
            secs = 0.0
            for task in tasks:
                call_id = f"{run_id}/{p.id}/{task.key}"
                if task.key == "interactions" and len(cast_here) < 2:
                    continue
                instruction = task.instruction.format(cast_here=", ".join(cast_here))
                messages = [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user_message(book, p, numbered, known, instruction)},
                ]
                resp = call(call_id, p.id, messages, inline_schema(task.model), task.key)
                errors += "error" in resp
                secs += resp.get("latency_s", 0)
                try:
                    parsed = task.model.model_validate_json(resp["text"])
                except ValidationError as e:
                    rejected.write(json.dumps({"passage": p.id, "call": call_id, "status": "rejected",
                                               "reason": "output did not match schema",
                                               "detail": str(e)[:500]}) + "\n")
                    pc[f"{task.key}_unparsable"] += 1
                    continue

                recs = []
                for field, kind in task.fields.items():
                    value = getattr(parsed, field)
                    for item in value if isinstance(value, list) else [value]:
                        data = item.model_dump(exclude={"evidence"})
                        recs.append(check(book, p, sents, kind, data, item.evidence, call_id))

                failed = [i for i, r in enumerate(recs) if r["status"] == "rejected"]
                if failed:
                    listing = "\n".join(
                        f"{k}. {label(recs[i])}: {recs[i]['reason']}. You cited: {recs[i]['evidence']['sentences']}"
                        for k, i in enumerate(failed, 1)
                    )
                    rmsgs = messages + [
                        {"role": "assistant", "content": resp["text"]},
                        {"role": "user", "content": REPAIR.format(items=listing)},
                    ]
                    rid = f"{call_id}/repair"
                    rresp = call(rid, p.id, rmsgs, repair_schema, "repairs")
                    errors += "error" in rresp
                    try:
                        fixes = {f.n: f.evidence for f in Repairs.model_validate_json(rresp["text"]).fixes}
                    except ValidationError:
                        fixes = {}
                    for k, i in enumerate(failed, 1):
                        first = recs[i]
                        first_attempt = {"sentences": first["evidence"]["sentences"], "reason": first["reason"]}
                        if fixes.get(k):
                            again = check(book, p, sents, first["type"], first["data"], fixes[k], rid)
                            again["first_attempt"] = first_attempt
                            recs[i] = again
                        else:
                            first["reason"] += "; withdrawn in repair" if k in fixes else "; not repaired"
                        if recs[i]["status"] == "verified":
                            repaired += 1
                        pc["repaired" if recs[i]["status"] == "verified" else "repair_failed"] += 1

                for r in recs:
                    total += 1
                    if r["status"] == "verified":
                        ok += 1
                        if r["type"] == "character":
                            cast[r["data"]["name"]] += 1
                            if r["data"]["name"] not in cast_here:
                                cast_here.append(r["data"]["name"])
                    (facts if r["status"] == "verified" else rejected).write(
                        json.dumps(r, ensure_ascii=False) + "\n")
                    pc[f"{r['type']}_{r['status']}"] += 1
                facts.flush()
                rejected.flush()
            counts.update(pc)
            progress.write(json.dumps({"passage": p.id, "call_errors": errors, "counts": dict(pc),
                                       "at": datetime.now(timezone.utc).isoformat()}) + "\n")
            progress.flush()
            log(f"[{n}/{len(plist)}] {p.id}: {ok}/{total} facts verified ({repaired} after repair), "
                f"{len(cast_here)} characters, {secs:.0f}s")

    manifest["backend"] = backend.describe()  # again, now that the model is loaded
    manifest["finished"] = datetime.now(timezone.utc).isoformat()
    manifest["counts"] = dict(sorted(counts.items()))
    manifest["cast"] = dict(cast.most_common())
    (out / "run.json").write_text(json.dumps(manifest, indent=2))
    return out


def recheck(out: Path, book: Book, log=print) -> dict:
    """Apply the current checker to a run read under an older one, without calling a model.

    Each verified fact is checked again against the same cited sentences. Facts that the
    current rules refuse move to rejected.jsonl, carrying their old record and the checker
    that had accepted them. Nothing is edited and nothing is lost: the old facts.jsonl is
    kept beside the new one. Rejected items stay rejected, because the rules only got stricter;
    and a refused fact gets no repair round, since that would need the model."""
    out = Path(out)
    manifest = json.loads((out / "run.json").read_text())
    if manifest["book"]["sha256"] != book.sha256:
        raise ValueError(f"{out.name} was read from a different file of {book.title}")
    old = manifest.get("checker", 1)
    if old == CHECKER:
        log(f"{out.name} is already checked by checker {CHECKER}")
        return {"checker": CHECKER, "moved": 0}
    by_id = {p.id: p for p in passages(book)}
    sents = {}
    facts = _jsonl(out / "facts.jsonl")
    kept, moved = [], []
    at = datetime.now(timezone.utc).isoformat()
    for r in facts:
        p = by_id[r["passage"]]
        if p.id not in sents:
            sents[p.id] = p.numbered_text(book)[1]
        again = check(book, p, sents[p.id], r["type"], r["data"], r["evidence"]["sentences"], r["call"])
        if again["status"] == "verified":
            kept.append(r)
            continue
        moved.append({**r, "status": "rejected", "support": again["support"], "reason": again["reason"],
                      "recheck": {"checker": CHECKER, "at": at, "was": "verified", "by_checker": old}})
    (out / "facts.jsonl").rename(out / f"facts.checker-{old}.jsonl")
    with open(out / "facts.jsonl", "w") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in kept)
    with open(out / "rejected.jsonl", "a") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in moved)

    counts = Counter(manifest.get("counts", {}))
    for r in moved:
        counts[f"{r['type']}_verified"] -= 1
        counts[f"{r['type']}_rejected"] += 1
    cast = Counter(r["data"]["name"] for r in kept if r["type"] == "character")
    summary = {"at": at, "from_checker": old, "checker": CHECKER, "moved": len(moved),
               "by_support": dict(Counter(r["support"] for r in moved)),
               "kept_as": f"facts.checker-{old}.jsonl"}
    manifest.setdefault("rechecks", []).append(summary)
    manifest.update(checker=CHECKER, counts=dict(sorted(counts.items())), cast=dict(cast.most_common()))
    (out / "run.json").write_text(json.dumps(manifest, indent=2))
    log(f"checker {old} -> {CHECKER}: {len(facts)} facts, {len(moved)} moved to rejected {summary['by_support']}")
    return summary
