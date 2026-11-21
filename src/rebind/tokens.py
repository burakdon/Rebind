"""One style-neutral record of the reading, for any number of drawings.

Reading the book with a model is the slow part and is done once. This step calls
no model: it gathers what the run already holds into `book.json`, from the whole
book down to each sentence, with nothing in it about how to draw. A style (the
survey map, the lightbox, whatever comes next) is then a small renderer over this
one file, so a new style costs no reading.

Two kinds of field, and `fields` in the file says which is which:

  read   a model's judgement, kept only because code checked its cited sentences
         (place, tension, warmth, people, meetings, objects, events)
  code   counted or matched by code from the text itself
         (offsets, word counts, speech, names found in a sentence, citation counts)

Sentences are stored as columns (one list per attribute) to keep the file small.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import entities as E
from . import labels as LB
from .compose import _object_kind, _roman
from .source import ROOT, Book, passages
from .verify import _find_all, normalise

FIELDS = {
    "places[].name": "read: a place the settings pass chose for at least one passage",
    "people[]": "read: names the reader verified, merged into one person by the entity pass; `as` says why each "
                "counts: a name, a description the book writes with a capital (title), or a named person's relation",
    "passages[].place": "read: where the passage takes place (settings pass), with its basis and any flags",
    "passages[].at": "code: the place to stand on; a passage set 'unclear' or 'elsewhere' keeps the place before it",
    "passages[].tension, .warmth": "read: 0-10, with the reader's one-sentence reason and cited sentences in .tone",
    "passages[].people": "read: persons with a verified character fact in this passage, and what they are called here",
    "passages[].meetings, .objects, .events": "read: verified facts of those types, each with its fact id and spans",
    "sentences.start, .end": "code: exact offsets of the sentence in the source file",
    "sentences.words": "code: number of words",
    "sentences.speech": "code: 1 if any of the sentence lies inside quotation marks",
    "sentences.people": "code: persons named in the sentence, by a name the reader verified for them in this "
                        "passage, or by a name it only ever verified for one person in the whole book; "
                        "pronouns are not resolved, so 'she' names nobody",
    "sentences.places": "code: places named in the sentence, by a name in the book's own gazetteer",
    "sentences.cited": "code: how many accepted facts cite this sentence",
    "sentences.feeling, .pace": "read: the first reading's labels for the sentence. feeling 0 neither, 1 warm, 2 cold; "
                                "pace 0 calm, 1 tense; -1 where the reading has no usable answer",
    "sentences.feeling_b, .pace_b": "read: the same labels from the second reading, which asks in other words",
    "chapters[]": "code: passages grouped by chapter; tension is the highest in the chapter, warmth the mean",
}


def _named(text: str, names: list[tuple[str, int]]) -> list[int]:
    """Which of `names` (normalised phrase, owner) occur in `text` as whole words.

    Longest first, and a matched stretch is blanked, so "Miss Darcy" is not also
    counted as "Darcy".
    """
    hay, found = normalise(text).text, []
    for frag, owner in names:
        hits = _find_all(hay, frag, 0)
        if not hits:
            continue
        if owner not in found:
            found.append(owner)
        for i in hits:
            hay = hay[:i] + " " * len(frag) + hay[i + len(frag):]
    return found


def _phrase(name: str) -> str:
    return normalise(name).text.strip(' "')


FIGURE_MIN = 3   # verified facts a description needs before it counts as a person


def figure(entity: dict, person_names: set[str]) -> str | None:
    """Whether an entity can own a column, and why: 'name', 'title' or 'relation'. None if it cannot.

    A person the reader named always can. A description can only if the book itself uses it as a name:
    it is written with a capital after "the" ("the Ghost"), or it is a named person's relation
    ("Scrooge's nephew"). "the clerk" or "the fire" cannot, because nothing in the words says who is meant.
    """
    if entity["kind"] == "person":
        return "name"
    if entity["kind"] != "reference":
        return None
    name = entity["canonical"]
    words = name.split()
    if len(words) >= 2 and words[0].lower() == "the" and words[1][:1].isupper():
        return "title"
    m = re.fullmatch(r"(.+?)['’]s [a-z][a-z-]+", name)
    if m and m.group(1) in person_names:
        return "relation"
    return None


def tokenize(run_dir: Path, book: Book, out_dir: Path | None = None, log=print) -> Path:
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "run.json").read_text())
    facts = [json.loads(l) for l in open(run_dir / "facts.jsonl")]
    if (run_dir / "settings" / "settings.jsonl").exists():
        settings = {r["passage"]: r for r in map(json.loads, open(run_dir / "settings" / "settings.jsonl"))}
        gazetteer = json.loads((run_dir / "settings" / "gazetteer.json").read_text())
    else:  # `rebind locate` was not run (the scarf does not need it): no passage has a place
        settings = {pid: {"passage": pid, "setting": "elsewhere"} for pid in manifest["passages"]}
        gazetteer = {}
    names = E.load(run_dir)
    by_id = {p.id: p for p in passages(book)}
    plist = [by_id[i] for i in manifest["passages"] if i in settings]
    by_passage = defaultdict(list)
    for f in facts:
        by_passage[f["passage"]].append(f)

    # People: every figure (see figure()) with at least one verified character fact, most mentioned first.
    canon = {e["id"]: e for e in names.values()}
    person_names = {n for e in canon.values() if e["kind"] == "person" for n in [e["canonical"], *e["names"]]}
    counts_as = {eid: figure(e, person_names) for eid, e in canon.items()}
    cited = Counter(e["id"] for f in facts if f["type"] == "character" and (e := names.get(E.key(f["data"]["name"]))))
    for eid, why in counts_as.items():  # one capital letter is not yet a name: a description needs FIGURE_MIN facts
        if why in ("title", "relation") and cited[eid] < FIGURE_MIN:
            counts_as[eid] = None
    person_of, mentions = {}, Counter()
    for f in facts:
        if f["type"] == "character":
            e = names.get(E.key(f["data"]["name"]))
            if e and counts_as[e["id"]]:
                person_of[f["id"]] = e
                mentions[e["id"]] += 1
    order = [eid for eid, _ in mentions.most_common()]
    index = {eid: i for i, eid in enumerate(order)}
    people = [{"id": eid, "name": canon[eid]["canonical"], "names": canon[eid]["names"], "mentions": mentions[eid],
               "as": counts_as[eid],
               "title": E.title_gender(canon[eid]["canonical"]) or next(
                   (g for g in map(E.title_gender, canon[eid]["names"]) if g), None)} for eid in order]

    # Places, in the order the story first goes there.
    at, prev = [], None
    for p in plist:
        s = settings[p.id]["setting"]
        if s in ("unclear", "elsewhere"):
            at.append((prev, "carried"))
        else:
            at.append((s, "set"))
            prev = s
    first = next((w for w, how in at if how == "set"), None)
    at = [(w or first, how) for w, how in at]
    place_order = list(dict.fromkeys(w for w, _ in at if w))
    count = Counter(w for w, _ in at)
    places = [{"name": n, "passages": count[n], "first_chapter": next(p.chapter for p, (w, _) in zip(plist, at) if w == n),
               "names": gazetteer.get(n, [n])} for n in place_order]
    place_names = sorted(((_phrase(alias), n) for n, aliases in gazetteer.items() for alias in aliases),
                         key=lambda t: -len(t[0]))
    gaz_index = {n: i for i, n in enumerate(gazetteer)}

    # A name the reader only ever verified for one person names that person anywhere ("Mr. Bennet").
    # A name it used for more than one ("Miss Bennet") counts only in passages where it said who.
    owners = defaultdict(set)
    for f in facts:
        if f["id"] in person_of:
            owners[_phrase(f["data"]["called_here"])].add(index[person_of[f["id"]]["id"]])
    everywhere = {frag: next(iter(who)) for frag, who in owners.items() if len(who) == 1}

    out_passages = []
    S = {k: [] for k in ("start", "end", "passage", "words", "speech", "people", "places", "cited",
                         "feeling", "pace", "feeling_b", "pace_b")}
    read_a, read_b = LB.load(run_dir, "a"), LB.load(run_dir, "b")
    FEEL, PACE = {"neither": 0, "warm": 1, "cold": 2}, {"calm": 0, "tense": 1}
    for i, p in enumerate(plist):
        fs, s = by_passage[p.id], settings[p.id]
        tone = next((f for f in fs if f["type"] == "tone"), None)
        seen = defaultdict(list)
        for f in fs:
            if f["type"] == "character" and f["id"] in person_of:
                seen[person_of[f["id"]]["id"]].append(f)
        meetings = []
        for f in fs:
            if f["type"] == "interaction":
                who = []
                for n in f["data"]["characters"]:
                    e = names.get(E.key(n))
                    if e and e["id"] in index and e["id"] not in who:
                        who.append(e["id"])
                meetings.append({"who": who, "kind": f["data"]["kind"], "summary": f["data"]["summary"],
                                 "fact": f["id"], "spans": f["evidence"]["spans"]})

        # Sentences. A name counts for a person only if the reader verified it for them in this passage.
        here = {**everywhere, **{_phrase(f["data"]["called_here"]): index[eid] for eid, cf in seen.items() for f in cf}}
        called = sorted(here.items(), key=lambda t: -len(t[0]))
        cited = Counter(tuple(sp) for f in fs for sp in f["evidence"]["spans"])
        first_sentence = len(S["start"])
        for para in p.sentences(book):
            inside = False
            for sp in para:
                text = book.text[sp.start:sp.end]
                opens, closes = text.count("“"), text.count("”")
                straight = text.count('"')  # editions with plain " marks: each one opens or closes speech
                S["start"].append(sp.start)
                S["end"].append(sp.end)
                S["passage"].append(i)
                S["words"].append(len(text.split()))
                S["speech"].append(1 if inside or opens or straight else 0)
                S["people"].append(_named(text, called))
                S["places"].append([gaz_index[n] for n in _named(text, place_names)])
                S["cited"].append(cited.get((sp.start, sp.end), 0))
                last_open, last_close = text.rfind("“"), text.rfind("”")
                inside = last_open > last_close if (opens or closes) else inside
                if straight % 2:
                    inside = not inside

        count = len(S["start"]) - first_sentence
        for suffix, got in (("", read_a.get(p.id)), ("_b", read_b.get(p.id))):
            ok = bool(got) and got["n"] == count
            S["feeling" + suffix] += [FEEL[f] for f in got["feeling"]] if ok else [-1] * count
            S["pace" + suffix] += [PACE[f] for f in got["pace"]] if ok else [-1] * count
        out_passages.append({
            "id": p.id, "chapter": p.chapter, "start": p.start, "end": p.end, "words": p.n_words,
            "sentences": [first_sentence, len(S["start"]) - first_sentence],
            "place": {k: s.get(k) for k in ("setting", "basis", "rationale", "step", "flags", "spans", "call")},
            "at": {"place": at[i][0], "how": at[i][1]},
            "tension": tone["data"]["tension"] if tone else None,
            "warmth": tone["data"]["warmth"] if tone else None,
            "tone": {"reason": tone["data"]["reason"], "fact": tone["id"], "spans": tone["evidence"]["spans"]} if tone else None,
            "people": [{"id": eid, "called": sorted({f["data"]["called_here"] for f in cf}),
                        "facts": [f["id"] for f in cf], "spans": [sp for f in cf for sp in f["evidence"]["spans"]]}
                       for eid, cf in seen.items()],
            "meetings": meetings,
            "objects": [{"name": f["data"]["name"], "kind": _object_kind(f["data"]["name"]),
                         "description": f["data"].get("description"), "fact": f["id"], "spans": f["evidence"]["spans"]}
                        for f in fs if f["type"] == "object"],
            "events": [{"summary": f["data"]["summary"], "fact": f["id"], "spans": f["evidence"]["spans"]}
                       for f in fs if f["type"] == "event"],
        })

    chapters = []
    for c in sorted({p.chapter for p in plist}):
        idx = [i for i, p in enumerate(plist) if p.chapter == c]
        tens = [out_passages[i]["tension"] for i in idx if out_passages[i]["tension"] is not None]
        warm = [out_passages[i]["warmth"] for i in idx if out_passages[i]["warmth"] is not None]
        chapters.append({"n": c, "label": _roman(c), "passages": [idx[0], len(idx)],
                         "places": list(dict.fromkeys(at[i][0] for i in idx if at[i][0])),
                         "tension": max(tens) if tens else None,
                         "warmth": round(sum(warm) / len(warm), 2) if warm else None})

    doc = {
        "book": {"title": book.title, "author": book.author, "slug": book.slug, "sha256": book.sha256,
                 "chapter_word": book.config.get("chapter_word", "Chapter")},
        "run": {"id": manifest["run_id"], "model": manifest["backend"]["model"],
                "digest": manifest["backend"].get("digest"), "prompt": manifest["prompt_version"],
                "checker": manifest.get("checker", 1)},
        "generated": datetime.now(timezone.utc).isoformat(),
        "fields": FIELDS,
        "readings": {"a": len(read_a), "b": len(read_b)},
        "gazetteer": list(gazetteer),
        "places": places, "people": people, "chapters": chapters, "passages": out_passages, "sentences": S,
    }
    out = Path(out_dir or ROOT / "site" / "data" / book.slug)
    out.mkdir(parents=True, exist_ok=True)
    (out / "book.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    text = {"file": manifest["book"]["file"], "sha256": book.sha256,
            "passages": {p.id: book.text[p.start:p.end] for p in plist}}
    (out / "text.json").write_text(json.dumps(text, ensure_ascii=False))
    n = len(S["start"])
    log(f"{len(plist)} passages, {n} sentences ({sum(S['speech'])} speech, {sum(1 for x in S['people'] if x)} "
        f"naming a person, {sum(1 for x in S['cited'] if x)} cited), {len(people)} people, {len(places)} places "
        f"-> {out / 'book.json'}")
    return out
