"""Merge the names a reader gave characters into one entity per person.

The reader names people passage by passage, so one woman can appear as
"Elizabeth Bennet", "Lizzy" and "Miss Elizabeth Bennet", and Charlotte Lucas
becomes "Mrs. Collins" halfway through. This pass groups those names. It never
edits the facts: it writes a mapping from each name to an entity, and every
entry in that mapping says which step decided it and why.

Steps, each logged in decisions.jsonl:
  R1 spelling   Names that differ only in case, curly quotes or spacing are one name. (code)
  M1 anchors    For each frequent name (>= ANCHOR_MIN mentions) the model names the fullest
                name of the same character; linked names form one entity. (one model call)
  M2 tail       Each rarer name is attached to an existing entity or starts a new one,
                in small batches, frequent names first. (model calls)
  R2 titles     A person may not mix male titles (Mr, Sir, Colonel...) with female ones
                (Mrs, Miss, Lady); the minority side is split off. (code)
  R3 default    A name the model left out keeps an entity of its own. (code)
  R4 references "her sister", "the late Mr. Darcy", "Mr. Wickham's father", "Mr. and Mrs.
                Collins", "me": descriptions whose referent changes from passage to passage.
                They are never merged at book level and the model is not asked about them. (code)
  R5 given names Two different given names cannot be one person ("Anne" is not "Georgiana"),
                except a standard nickname from NICKNAMES (Lizzy, Kitty...). (code)
  R6 Miss/Mrs   One woman is not both "Miss X" and "Mrs. X" for the same surname X. (code)
  R7 surnames   A man's surname and a woman's maiden name ("Miss X", "Jane X") are fixed: one
                person cannot carry two. Married forms ("Mrs. X", "Lady X") are exempt. (code)
  R8 same name  Person entities with the same given name (through NICKNAMES) and the same
                fixed surname are one person: "Kitty Bennet" and "Catherine Bennet". (code)
  R2, R5, R6 and R7 split the smaller side off as its own entity and keep the overruled
  model decision in the log.

The model must also say what each merge rests on (`basis`). "knowledge of the
novel" means the examples alone do not show it, so such merges are flagged for
the hand check rather than trusted.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


from .backends import Backend

ANCHOR_MIN = 5
BATCH = 8
HEAVY = 50  # mentions; merging two names this frequent is flagged for the hand check
RATIONALE_MAX = 100
PARAMS = {"temperature": 0.0, "seed": 1342, "max_tokens": 3600}  # M1 prompt is ~4,350 tokens; context is 8,192
PRONOUNS = {"he", "she", "him", "her", "his", "hers", "they", "them", "their", "i", "me", "my", "you",
            "your", "we", "us", "our", "it", "its", "himself", "herself", "themselves"}
MALE = {"mr", "sir", "colonel", "captain", "lord", "general", "master", "dr", "rev", "mister"}
FEMALE = {"mrs", "miss", "lady", "madam", "madame", "mistress", "dame"}
TITLES = MALE | FEMALE
REF_START = {"the", "a", "an", "her", "his", "my", "your", "our", "their", "its", "this", "that", "these",
             "those", "one", "some", "all", "both", "two", "three", "four", "several", "another", "every",
             "each", "any", "no", "old", "young", "poor", "dear", "little"}
PARTICLES = {"de", "du", "van", "von", "la", "le", "of", "d'", "da", "di", "st"}
MARRIED = {"mrs", "lady", "madam", "madame", "mistress", "dame"}
PLURAL_START = {"all", "both", "two", "three", "four", "several", "these", "those", "some"}
# Standard English nicknames: ordinary knowledge of naming, not of any one novel.
NICKNAMES = {
    "lizzy": "elizabeth", "lizzie": "elizabeth", "eliza": "elizabeth", "liz": "elizabeth", "beth": "elizabeth",
    "betsy": "elizabeth", "bess": "elizabeth", "kitty": "catherine", "kate": "catherine", "jenny": "jane",
    "polly": "mary", "molly": "mary", "sally": "sarah", "nancy": "anne", "harry": "henry", "jack": "john",
    "will": "william", "bill": "william", "charlie": "charles", "fanny": "frances", "patty": "martha",
    "nelly": "eleanor", "tom": "thomas", "ned": "edward", "teddy": "edward", "georgy": "georgiana",
}
Kind = Literal["person", "group", "not_a_person"]
Basis = Literal[
    "same name written differently",
    "nickname or first name",
    "title or surname form",
    "married name",
    "relation shown in the examples",
    "knowledge of the novel",
    "no merge",
]

SYSTEM = """You are building the cast list of a novel from names that a reader model wrote down passage by passage.

Several names may refer to the same character: a nickname, a first name alone, a surname alone, a title, a married name. Different people often share a surname (Mr. Bennet, Mrs. Bennet and the Bennet daughters are different people), so never merge on a shared surname alone.

Some names are not individual characters: groups of people ("the officers") or places, objects and other things the reader mislabelled ("Pemberley", "the two third"). Label them.

For every decision give `basis`, what it rests on. Choose "knowledge of the novel" whenever the example sentences shown do not themselves establish it."""

ANCHOR_TASK = """These names were each used for a character in at least {n} passages. For each name give:
- `same_as`: the name in this list that is the fullest usual name of the same character. Give the name itself if it is that fullest name, or if no other name in the list refers to the same character or group.
- `kind`: person, group, or not_a_person.

{listing}"""

TAIL_TASK = """Known entities so far (id: canonical name, kind):
{entities}

For each name below, give `same_as`: the id of the known entity it refers to, or "new_person", "new_group" or "not_a_person". Also give its `kind`.

{listing}"""


def key(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace("’", "'").replace("‘", "'")).strip().casefold()


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", key(name)).strip("-")


def title_gender(name: str) -> str | None:
    first = re.sub(r"[^a-z]", "", key(name).split(" ")[0]) if name.strip() else ""
    return "male" if first in MALE else "female" if first in FEMALE else None


def words(name: str) -> list[str]:
    return [w for w in re.sub(r"[^a-z' ]", " ", key(name)).split() if w]


def reference_kind(name: str) -> str | None:
    """R4: None for a proper name; otherwise "group" or "reference"."""
    w = words(name)
    if not w:
        return "reference"
    plural = (w[0] in PLURAL_START or " and " in f" {key(name)} " or "&" in name
              or (w[-1].endswith("s") and not w[-1].endswith(("ss", "'s")) and w[0] in REF_START))
    if (w[0] in REF_START or key(name) in PRONOUNS or "'s " in key(name) + " " or plural):
        return "group" if plural else "reference"
    return None


def parse_name(name: str, surnames: set[str] = frozenset()) -> tuple[str | None, str | None, str | None]:
    """(title, given name, surname) as far as the name shows them.
    "Mr. Fitzwilliam Darcy" -> (mr, fitzwilliam, darcy); "Miss de Bourgh" -> (miss, None, de bourgh);
    "Lizzy" -> (None, elizabeth, None); "Darcy" -> (None, None, None) when darcy is a known surname."""
    w = words(name)
    title = w[0] if w and w[0] in TITLES else None
    if title:
        w = w[1:]
    i = next((j for j, t in enumerate(w) if t in PARTICLES), len(w))  # surname particles start the surname
    head, tail = w[:i], w[i:]
    if len(head) >= 2:
        given, surname = head[0], " ".join(head[1:] + tail)
    elif len(head) == 1 and tail:
        given, surname = head[0], " ".join(tail)
    elif len(head) == 1 and title:
        given, surname = None, head[0]
    elif len(head) == 1 and head[0] not in surnames:
        given, surname = head[0], None
    else:
        given, surname = None, " ".join(tail) or None
    return title, (NICKNAMES.get(given, given) if given else None), surname


def given_name(name: str, surnames: set[str]) -> str | None:
    """R5: the given name a name carries, through the nickname table, if it carries one."""
    return parse_name(name, surnames)[1]


def fixed_surname(name: str) -> str | None:
    """R7: the surname a name fixes, unless the name is a married form."""
    title, _, surname = parse_name(name)
    return None if title in MARRIED else surname


def _example(f: dict, width: int = 70) -> str:
    """The cited sentence, cut to a window around where the passage names the person."""
    text = re.sub(r"\s+", " ", f["evidence"].get("source_text", ""))
    called = f["data"]["called_here"]
    m = re.search(re.escape(called).replace("\\ ", r"\s+"), text, re.I) if called else None
    mid = m.start() + len(called) // 2 if m else 0
    a, b = max(0, mid - width), min(len(text), mid + width)
    clip = ("…" if a else "") + text[a:b] + ("…" if b < len(text) else "")
    return f'ch.{f["chapter"]} as "{called}": {clip}'


def gather(facts: list[dict]) -> dict[str, dict]:
    """Each distinct spelling (R1) with its count and two example sentences, preferring
    examples where the passage actually uses a name rather than a pronoun."""
    names: dict[str, dict] = {}
    for f in facts:
        if f["type"] != "character":
            continue
        k = key(f["data"]["name"])
        n = names.setdefault(k, {"spellings": Counter(), "facts": []})
        n["spellings"][f["data"]["name"]] += 1
        n["facts"].append(f)
    out = {}
    for k, n in names.items():
        named = [f for f in n["facts"] if key(f["data"]["called_here"]) not in PRONOUNS] or n["facts"]
        picks = [named[0]] + ([named[-1]] if len(named) > 1 and named[-1]["chapter"] != named[0]["chapter"] else [])
        out[k] = {
            "name": n["spellings"].most_common(1)[0][0],
            "spellings": dict(n["spellings"]),
            "mentions": len(n["facts"]),
            "chapters": sorted({f["chapter"] for f in n["facts"]}),
            "examples": [_example(f) for f in picks],
        }
    return dict(sorted(out.items(), key=lambda kv: (-kv[1]["mentions"], kv[0])))


def _listing(items: list[dict]) -> str:
    return "\n".join(
        f'- "{it["name"]}" ({it["mentions"]} mentions, chapters {it["chapters"][0]}–{it["chapters"][-1]})\n'
        + "\n".join(f"    {e}" for e in it["examples"])
        for it in items
    )


def per_name_schema(names: list[str], targets: list[str]) -> dict:
    """One required slot per name, in order. Open-ended lists let a small model loop
    (it once repeated a name until it ran out of tokens); fixed slots cannot, and the
    rationale is capped so it cannot run on either."""
    slot = {
        "type": "object",
        "properties": {
            "same_as": {"enum": targets},
            "kind": {"enum": list(Kind.__args__)},
            "basis": {"enum": list(Basis.__args__)},
            "rationale": {"type": "string", "maxLength": RATIONALE_MAX},
        },
        "required": ["same_as", "kind", "basis", "rationale"],
        "additionalProperties": False,
    }
    return {"type": "object", "properties": {n: slot for n in names}, "required": names,
            "additionalProperties": False}


def parse_slots(text: str, names: list[str], targets: list[str]) -> dict[str, dict]:
    """Keep only well-formed slots; anything missing is handled by R3."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
    out = {}
    for n in names:
        v = data.get(n) if isinstance(data, dict) else None
        if (isinstance(v, dict) and v.get("same_as") in targets and v.get("kind") in Kind.__args__
                and v.get("basis") in Basis.__args__ and isinstance(v.get("rationale"), str)):
            out[n] = v
    return out


def resolve(run_dir: Path, backend: Backend, log=print) -> Path:
    run_dir = Path(run_dir)
    out = run_dir / "entities"
    out.mkdir(exist_ok=True)
    facts = [json.loads(l) for l in open(run_dir / "facts.jsonl")]
    names = gather(facts)
    started = datetime.now(timezone.utc)

    entities: dict[str, dict] = {}  # id -> {canonical, kind, members[keys]}
    decision: dict[str, dict] = {}  # name key -> how it was placed
    flags: dict[str, list[str]] = defaultdict(list)
    calls = open(out / "calls.jsonl", "w")

    def call(call_id, task, schema, name):
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
        try:
            resp = backend.chat(messages, schema, schema_name=name, **PARAMS)
        except Exception as e:
            resp = {"text": "", "error": repr(e)}
        calls.write(json.dumps({"id": call_id, "messages": messages, **resp}, ensure_ascii=False) + "\n")
        calls.flush()
        return resp.get("text", "")

    def new_entity(canonical_key, kind):
        eid = slug(names[canonical_key]["name"])
        while eid in entities:
            eid += "-2"
        entities[eid] = {"canonical": names[canonical_key]["name"], "kind": kind, "members": []}
        return eid

    def place(k, eid, step, basis, rationale, call_id=None):
        entities[eid]["members"].append(k)
        decision[k] = {"entity": eid, "step": step, "basis": basis, "rationale": rationale, "call": call_id}

    # R4: references and groups are kept apart, unmerged.
    unmergeable: set[str] = set()
    for k, v in names.items():
        if (kind := reference_kind(v["name"])):
            unmergeable.add(eid := new_entity(k, kind))
            place(k, eid, "R4", "no merge",
                  "A description, not a name: who it means depends on the passage, so it is not merged.")

    # M1: each frequent name points at the fullest name of the same character (or itself).
    anchors = [k for k, v in names.items() if v["mentions"] >= ANCHOR_MIN and k not in decision]
    labels = [names[k]["name"] for k in anchors]
    by_name = dict(zip(labels, anchors))
    log(f"{len(names)} distinct names; {len(anchors)} anchors (>= {ANCHOR_MIN} mentions)")
    slots = parse_slots(call("M1", ANCHOR_TASK.format(n=ANCHOR_MIN, listing=_listing([names[k] for k in anchors])),
                             per_name_schema(labels, labels), "anchors"), labels, labels)
    # Groups are the connected components of the same_as links (union-find).
    parent = {k: k for k in anchors}

    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for n, v in slots.items():
        a, b = root(by_name[n]), root(by_name[v["same_as"]])
        if a != b:
            parent[a] = b
    comps = defaultdict(list)
    for k in anchors:
        comps[root(k)].append(k)
    for members in comps.values():
        # Canonical: the name most often pointed at, then the most mentioned.
        votes = Counter(by_name[slots[names[k]["name"]]["same_as"]] for k in members if names[k]["name"] in slots)
        canon = max(members, key=lambda k: (votes[k], names[k]["mentions"]))
        cslot = slots.get(names[canon]["name"])
        if not cslot:
            for k in members:
                place(k, new_entity(k, "person"), "R3", "no merge", "Left out by the model; kept as its own entity.")
            continue
        eid = new_entity(canon, cslot["kind"])
        for k in members:
            v = slots.get(names[k]["name"])
            if v:
                place(k, eid, "M1", v["basis"] if k != canon else "no merge", v["rationale"], "M1")
            else:
                place(k, eid, "R3", "no merge", "Left out by the model; joined through another name's link.")
        heavy = [names[k]["name"] for k in members if names[k]["mentions"] >= HEAVY]
        if len(heavy) > 1:
            for k in members:
                flags[k].append(f"merges several major names: {heavy}")

    # M2: the rest, frequent first, a few at a time; new entities become choices for later batches.
    tail = [k for k in names if k not in decision]
    for b in range(0, len(tail), BATCH):
        batch = tail[b:b + BATCH]
        # Nothing is attached to an R4 entity: "the housekeeper" is a different person in each passage.
        ids = [e for e, v in entities.items() if v["kind"] != "not_a_person" and e not in unmergeable]
        targets = ids + ["new_person", "new_group", "not_a_person"]
        listing_entities = "\n".join(f'{e}: {entities[e]["canonical"]}, {entities[e]["kind"]}' for e in ids)
        blabels = [names[k]["name"] for k in batch]
        cid = f"M2.{b // BATCH + 1:02d}"
        text = call(cid, TAIL_TASK.format(entities=listing_entities, listing=_listing([names[k] for k in batch])),
                    per_name_schema(blabels, targets), "assignments")
        slots = parse_slots(text, blabels, targets)
        for k in batch:
            v = slots.get(names[k]["name"])
            if not v:
                place(k, new_entity(k, "person"), "R3", "no merge", "Left out by the model; kept as its own entity.")
            elif v["same_as"] in entities:
                place(k, v["same_as"], "M2", v["basis"], v["rationale"], cid)
            else:
                kind = {"new_person": "person", "new_group": "group"}.get(v["same_as"], "not_a_person")
                place(k, new_entity(k, kind), "M2", "no merge", v["rationale"], cid)
        log(f"  tail {min(b + BATCH, len(tail))}/{len(tail)}: {len(entities)} entities")

    # R8: same given name and same fixed surname -> one person.
    def full_names(e):
        return {(g, sn) for k in e["members"]
                if (p := parse_name(names[k]["name"]))[1] and p[2] and p[0] not in MARRIED for g, sn in [p[1:]]}

    persons = sorted((e for e in entities if entities[e]["kind"] == "person"),
                     key=lambda e: -sum(names[k]["mentions"] for k in entities[e]["members"]))
    for i, a in enumerate(persons):
        for b in persons[i + 1:]:
            shared = full_names(entities[a]) & full_names(entities[b])
            if shared and entities[b]["members"]:
                g, sn = sorted(shared)[0]
                for k in list(entities[b]["members"]):
                    entities[b]["members"].remove(k)
                    was = decision[k]
                    place(k, a, "R8", "nickname or first name",
                          f"Same person as {a}: both are named {g.title()} {sn.title()} (nicknames resolved).")
                    decision[k]["overrode"] = was

    # R2, R5, R6, R7: name pairs that cannot be one person. The heavier side keeps the entity.
    def split(rule, label_of, why):
        for eid in list(entities):
            e = entities[eid]
            if e["kind"] != "person":
                continue
            sides = defaultdict(list)
            for k in e["members"]:
                if (lab := label_of(k, e)):
                    sides[lab].append(k)
            if len(sides) < 2:
                continue
            weight = {lab: sum(names[k]["mentions"] for k in ks) for lab, ks in sides.items()}
            keep = max(weight, key=lambda lab: (weight[lab], lab))
            kept = ", ".join(names[x]["name"] for x in sides[keep])
            for lab, ks in sides.items():
                if lab == keep:
                    continue
                ks = sorted(ks, key=lambda k: -names[k]["mentions"])
                nid = new_entity(ks[0], "person")
                for k in ks:
                    e["members"].remove(k)
                    was = decision[k]
                    place(k, nid, rule, "no merge", f"Split from {eid}: {why(lab, keep)} ({kept}).")
                    decision[k]["overrode"] = was

    split("R2", lambda k, e: title_gender(names[k]["name"]),
          lambda lab, keep: f"a {lab} title cannot name the same person as a {keep} one")

    def surnames(e):
        return {sn for k in e["members"] if (sn := parse_name(names[k]["name"])[2])}

    split("R5", lambda k, e: given_name(names[k]["name"], surnames(e)),
          lambda lab, keep: f"given name '{lab}' is not '{keep}' or a nickname of it")

    def miss_mrs(k, e):
        w = words(names[k]["name"])
        if len(w) == 2 and w[0] in ("miss", "mrs"):
            other = "mrs" if w[0] == "miss" else "miss"
            if any(words(names[x]["name"]) == [other, w[1]] for x in e["members"]):
                return w[0]
        return None

    split("R6", miss_mrs, lambda lab, keep: f"'{lab.title()}.' and '{keep.title()}.' with one surname are two women")
    split("R7", lambda k, e: fixed_surname(names[k]["name"]),
          lambda lab, keep: f"surname '{lab}' cannot also be '{keep}' for one person")

    calls.close()
    # Write the mapping, the entity table, and the flags for the hand check.
    with open(out / "decisions.jsonl", "w") as f:
        for k, v in names.items():
            d = decision[k]
            fl = list(flags[k])
            if d["basis"] == "knowledge of the novel":
                fl.append("rests on knowledge of the novel, not the examples")
            f.write(json.dumps({"name": v["name"], "spellings": v["spellings"], "mentions": v["mentions"],
                                **d, "flags": fl}, ensure_ascii=False) + "\n")
    table = []
    for eid, e in entities.items():
        if not e["members"]:
            continue
        ms = sorted(e["members"], key=lambda k: -names[k]["mentions"])
        chs = sorted({c for k in ms for c in names[k]["chapters"]})
        table.append({"id": eid, "canonical": e["canonical"], "kind": e["kind"],
                      "mentions": sum(names[k]["mentions"] for k in ms),
                      "names": [names[k]["name"] for k in ms], "first_chapter": chs[0], "last_chapter": chs[-1]})
    table.sort(key=lambda t: -t["mentions"])
    (out / "entities.json").write_text(json.dumps(table, indent=2, ensure_ascii=False))
    (out / "run.json").write_text(json.dumps({
        "source_run": run_dir.name, "backend": backend.describe(), "params": PARAMS, "anchor_min": ANCHOR_MIN,
        "batch": BATCH, "system_prompt": SYSTEM, "anchor_task": ANCHOR_TASK, "tail_task": TAIL_TASK,
        "started": started.isoformat(), "finished": datetime.now(timezone.utc).isoformat(),
        "counts": {"names": len(names), "entities": len(table),
                   **Counter(t["kind"] for t in table),
                   "by_step": Counter(d["step"] for d in decision.values()),
                   "flagged": sum(1 for k in names if flags[k] or decision[k]["basis"] == "knowledge of the novel")},
    }, indent=2))
    return out


def load(run_dir: Path) -> dict[str, dict]:
    """name key -> entity record, for looking up any character fact's entity."""
    out = Path(run_dir) / "entities"
    table = {t["id"]: t for t in json.loads((out / "entities.json").read_text())}
    return {key(d["name"]): table[d["entity"]] for d in map(json.loads, open(out / "decisions.jsonl"))}
