"""Small judgements that can be counted: two labels for every sentence.

A 0-10 score for a passage cannot be checked and cannot be explained except by a
story told afterwards. So this pass asks for nothing a person could not check in a
few seconds: for each sentence, is it warm, cold or neither, and is it tense or calm.
Everything built on it (a row's yarn, whether it is ridged) is then arithmetic on
these labels by a printed rule, so the explanation of a row IS how it was computed.

Three ways to run it, each written to its own folder under <run>/labels/:

  a          the first reading
  b          a second reading: the same question in different words, with the choices
             in the opposite order. Where a and b disagree the reader was not sure.
  a-swapped  reading a again with every character and place name replaced by a
             neutral one. If labels move more than they do between a and b, the reader
             was leaning on having seen this novel before.
  a-<tag>    reading a by a different model (--model, --tag), as an independent reader.

The model is not told which book it is reading. The schema has one slot per sentence
number, so it must label every sentence exactly once. A stopped pass resumes.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import entities as E
from .backends import Backend
from .source import Book, passages

PARAMS = {"temperature": 0.0, "seed": 1342}
FEELINGS = ["warm", "cold", "neither"]
PACES = ["tense", "calm"]

READINGS = {
    "a": {
        "system": """You label each sentence of one passage from a novel. Judge each sentence by what it says and how it is said here. Do not use outside knowledge of the novel.

For every numbered sentence give two labels: its feeling, then its pace.

feeling:
- warm: the sentence shows affection, kindness, pleasure, praise or ease between people.
- cold: the sentence shows dislike, contempt, anger, hurt, mockery or distance between people.
- neither: it shows neither, or you cannot tell.

pace:
- tense: something is at stake or unsettled in the sentence: a conflict, a worry, suspense, or strong feeling held back.
- calm: nothing is at stake in the sentence.

Label every sentence, including short ones.""",
        "task": "PASSAGE:\n<<<\n{numbered}\n>>>\n\nLabel sentences 1 to {n}.",
        "order": ("feeling", "pace"), "feelings": FEELINGS, "paces": PACES,
    },
    "b": {
        "system": """Below is one passage of a novel with its sentences numbered. Give each sentence two labels, going only by the words in front of you and not by anything else you may know about the book.

pace
- calm: nothing hangs on the sentence.
- tense: the sentence carries conflict, worry, suspense, or feeling that is being held in.

feeling
- neither: no clear feeling between people either way, or it is impossible to say.
- cold: unkind, scornful, angry, wounded, mocking or distant.
- warm: fond, kind, glad, admiring or at ease.

Every sentence gets both labels, however short it is: its pace, then its feeling.""",
        "task": "<<<\n{numbered}\n>>>\n\nThere are {n} sentences. Label each one.",
        "order": ("pace", "feeling"), "feelings": FEELINGS[::-1], "paces": PACES[::-1],
    },
}

# Neutral stand-ins for the names-swapped reading. None is an Austen name.
WOMEN = ["Agnes", "Clara", "Edith", "Flora", "Helen", "Ida", "Laura", "Martha", "Nora", "Ruth", "Susan", "Alice", "Rose",
         "Ellen", "Grace", "Esther", "Hannah", "Judith", "Miriam", "Naomi", "Rachel", "Tabitha", "Beatrice", "Cora",
         "Dora", "Eunice", "Gwen", "Hilda", "Irene", "Joan", "Lois", "Mabel", "Olive", "Phoebe", "Vera", "Winifred"]
MEN = ["Albert", "Bernard", "Cyril", "Donald", "Ernest", "Felix", "Gilbert", "Hubert", "Ivor", "Jasper", "Kenneth",
       "Leonard", "Morris", "Norman", "Oswald", "Percy", "Quentin", "Roland", "Stanley", "Tobias", "Victor", "Wilfred"]
SURNAMES = ["Ashby", "Barlow", "Calder", "Denham", "Ellery", "Farrow", "Garside", "Holt", "Ingram", "Jessop", "Kirby",
            "Lowther", "Marsden", "Norbury", "Oakes", "Penrose", "Quarles", "Radley", "Selby", "Thorne", "Upton",
            "Varley", "Wren", "Yardley", "Alston", "Birkett", "Corley", "Dunmore", "Enfield", "Foxley", "Gresham",
            "Hadlow", "Ibbot", "Jowett", "Kelsall", "Lindsey", "Mossop", "Nethercott", "Orrell", "Pickard", "Rudd",
            "Sowerby", "Tindall", "Underhill", "Vickers", "Whatmore", "Yarrow", "Aldous", "Brock", "Cobb", "Dacre",
            "Eames", "Fenn", "Gaunt", "Hesketh", "Ives", "Judd", "Keeble", "Lumb", "Mew", "Nunn", "Orme", "Pym"]
ESTATES = ["Ashcombe", "Brierley", "Coldwell", "Dunmere", "Elmstead", "Fernhill", "Greyholm", "Harcott", "Ivywell",
           "Kingsmead", "Larkfield", "Marwood", "Northby", "Oldacre", "Pinehurst", "Quarrington", "Redmere",
           "Stonely", "Thornwick", "Underwood", "Vale End", "Westbrook", "Yewdale", "Applegarth", "Bracken", "Copley"]
REAL_PLACES = {"london", "england", "kent", "brighton", "bath", "scotland", "derbyshire", "hertfordshire", "the",
               "street", "park", "house", "lodge", "lane", "woods", "of", "and", "de", "st", "city"}


def schema(n: int, reading: dict) -> dict:
    # One short string per sentence ("warm calm"), in the reading's own order: a third of the output of nested objects.
    first, second = (reading["feelings" if k == "feeling" else "paces"] for k in reading["order"])
    slot = {"type": "string", "enum": [f"{x} {y}" for x in first for y in second]}
    return {"type": "object", "additionalProperties": False, "required": [str(i) for i in range(1, n + 1)],
            "properties": {str(i): slot for i in range(1, n + 1)}}


def parse(text: str, n: int) -> tuple[list[str], list[str]]:
    ans = json.loads(text)
    words = [set(ans[str(i)].split()) for i in range(1, n + 1)]
    feeling = [next(f for f in FEELINGS if f in w) for w in words]
    pace = [next(p for p in PACES if p in w) for w in words]
    assert all(f in FEELINGS for f in feeling) and all(p in PACES for p in pace)
    return feeling, pace


def swap_table(run_dir: Path) -> dict[str, str]:
    """Every word of a verified character or place name -> a neutral stand-in, the same one everywhere."""
    table, pools = {}, {"female": iter(WOMEN), "male": iter(MEN), "surname": iter(SURNAMES), "place": iter(ESTATES)}
    people = json.loads((Path(run_dir) / "entities" / "entities.json").read_text())
    for e in sorted((e for e in people if e["kind"] == "person"), key=lambda e: -e["mentions"]):
        gender = next((g for g in map(E.title_gender, e["names"]) if g), None)
        for name in e["names"]:
            words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’-]+", name) if w.lower() not in E.TITLES and w[0].isupper()
                     and w.lower() not in REAL_PLACES]
            for k, w in enumerate(words):
                if w in table:
                    continue
                kind = "surname" if (k == len(words) - 1 and (len(words) > 1 or E.title_gender(name))) else (gender or "surname")
                table[w] = next(pools[kind], None) or next(pools["surname"])
    gaz_file = Path(run_dir) / "settings" / "gazetteer.json"
    gaz = json.loads(gaz_file.read_text()) if gaz_file.exists() else {}
    for names in gaz.values():
        for name in names:
            for w in re.findall(r"[A-Za-z][A-Za-z'’-]+", name):
                if w[0].isupper() and w.lower() not in REAL_PLACES and w not in table:
                    table[w] = next(pools["place"], None) or next(pools["surname"])
    return table


def swap(text: str, table: dict[str, str]) -> str:
    if not table:
        return text
    pattern = re.compile(r"\b(" + "|".join(sorted(map(re.escape, table), key=len, reverse=True)) + r")\b")
    return pattern.sub(lambda m: table[m.group(1)], text)


def label(run_dir: Path, book: Book, backend: Backend, reading: str = "a", swapped: bool = False,
          limit: int | None = None, tag: str | None = None, stride: int = 1, log=print) -> Path:
    run_dir, spec = Path(run_dir), READINGS[reading]
    # `tag` keeps another model's labels apart from the main reader's (labels/a-olmo).
    out = run_dir / "labels" / (reading + ("-swapped" if swapped else "") + (f"-{tag}" if tag else ""))
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((run_dir / "run.json").read_text())
    by_id = {p.id: p for p in passages(book)}
    plist = [by_id[i] for i in manifest["passages"]][:limit]
    # A slow model can do every `stride`-th passage first, so an even sample of the book is ready early.
    plist = plist[::stride] + [p for k, p in enumerate(plist) if k % stride]
    table = swap_table(run_dir) if swapped else {}
    meta = {"backend": backend.describe(), "params": PARAMS, "reading": reading, "swapped": swapped,
            "system": spec["system"], "task": spec["task"], "order": spec["order"],
            "feelings": spec["feelings"], "paces": spec["paces"], "swap_table": table}
    done = {}
    if (out / "labels.jsonl").exists():
        old = json.loads((out / "run.json").read_text()) if (out / "run.json").exists() else {}
        same = ("params", "system", "task", "order", "feelings", "paces", "swap_table")
        if {k: old.get(k) for k in same} != json.loads(json.dumps({k: meta[k] for k in same})) or \
                old.get("backend", {}).get("model") != meta["backend"].get("model"):
            raise ValueError(f"{out} holds labels from a different prompt; move them aside first")
        done = {r["passage"]: r for r in map(json.loads, open(out / "labels.jsonl")) if r["ok"]}
        (out / "labels.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in done.values()))
    (out / "run.json").write_text(json.dumps({**meta, "started": datetime.now(timezone.utc).isoformat()}, indent=2))

    rows, calls = open(out / "labels.jsonl", "a"), open(out / "calls.jsonl", "a")
    for k, p in enumerate(plist, 1):
        if p.id in done:
            continue
        numbered, sents = p.numbered_text(book)
        n = len(sents)
        messages = [{"role": "system", "content": spec["system"]},
                    {"role": "user", "content": spec["task"].format(numbered=swap(numbered, table), n=n)}]
        cid = f"labels/{out.name}/{p.id}"
        try:
            resp = backend.chat(messages, schema(n, spec), schema_name="labels", max_tokens=80 + 14 * n, **PARAMS)
        except Exception as e:  # a failed call is recorded, not hidden
            resp = {"text": "", "error": repr(e)}
        calls.write(json.dumps({"id": cid, "messages": messages, **resp}, ensure_ascii=False) + "\n")
        calls.flush()
        try:
            feeling, pace = parse(resp.get("text") or "", n)
            row = {"passage": p.id, "n": n, "feeling": feeling, "pace": pace, "ok": True, "call": cid}
        except (json.JSONDecodeError, AssertionError, KeyError, TypeError, StopIteration, AttributeError):
            row = {"passage": p.id, "n": n, "feeling": [], "pace": [], "ok": False, "call": cid}
        rows.write(json.dumps(row, ensure_ascii=False) + "\n")
        rows.flush()
        c = Counter(row["feeling"])
        log(f"[{k}/{len(plist)}] {p.id}: {n} sentences, {c['warm']} warm {c['cold']} cold, "
            f"{Counter(row['pace'])['tense']} tense{'' if row['ok'] else ' FAILED'} {resp.get('latency_s', 0):.0f}s")
    rows.close()
    calls.close()
    got = [json.loads(l) for l in open(out / "labels.jsonl")]
    meta.update(finished=datetime.now(timezone.utc).isoformat(),
                counts={"passages": len(got), "failed": sum(not r["ok"] for r in got),
                        "sentences": sum(r["n"] for r in got if r["ok"]),
                        "feeling": dict(Counter(f for r in got for f in r["feeling"])),
                        "pace": dict(Counter(f for r in got for f in r["pace"]))})
    (out / "run.json").write_text(json.dumps(meta, indent=2))
    return out


def load(run_dir: Path, name: str) -> dict[str, dict]:
    """passage id -> its labels for one reading, or {} if that reading has not been run."""
    f = Path(run_dir) / "labels" / name / "labels.jsonl"
    return {r["passage"]: r for r in map(json.loads, open(f)) if r["ok"]} if f.exists() else {}
