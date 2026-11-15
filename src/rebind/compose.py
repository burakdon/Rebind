"""Turn a reading into a map: every mark comes from cited facts by a stated rule.

The renderer only draws what this file decides. Each element in layout.json names
the rule that placed it (`rule`) and the facts it rests on (`facts`), and RULES below
is copied into the file so the map carries its own legend of decisions.

The map is read left to right like the book. Coordinates are in map units; the
sheet is SHEET_W x SHEET_H (a 36 x 24 inch print).
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import entities as E
from .source import ROOT, Book, passages

SHEET_W, SHEET_H = 36.0, 24.0
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 1.6, 2.2, 2.6
PATHS = 12             # the most-mentioned people get a path
LANE = 0.085          # map units between neighbouring lanes
GAP_MAX = 4            # an absence longer than this many passages breaks the path
BAND_MIN = 0.9         # smallest band height, map units
RIDGE_FLOOR = 0.15     # share of a passage's tension felt far from where it is set
SIGMA_X = 2.5          # in passages
SIGMA_Y = 0.9          # map units: how far a scene's hill spreads across the bands
INKS = ["#9b2f22", "#1f3f6b", "#3d6b3a", "#6b3d74", "#a8641c", "#2f6f73", "#7a5a2e", "#8a2f5a",
        "#4a4a8a", "#5f6b1f", "#9a4a3a", "#3a5a8a", "#6a6a6a", "#8a6a1a", "#2a6a4a", "#7a3a3a"]

RULES = {
    "L1": "Passages run left to right in book order, evenly spaced; chapters are marked along the edges.",
    "L2": "Each passage stands on the band of the place where it takes place (settings pass). A passage whose "
          "setting is 'unclear' or 'elsewhere' stays on the band of the passage before it.",
    "L3": "Bands are stacked top to bottom in the order the story first goes there; a band's height grows with "
          "the square root of the number of passages set there, so the home place does not crowd out the rest.",
    "L4": "Height is the reader's tension score (0-10), smoothed over about +-2.5 passages. It is full where the "
          f"passage is set and falls to {RIDGE_FLOOR:.0%} far from it, so one contour line is one point of tension "
          "where the scene is.",
    "L5": "The paper's wash is the reader's warmth score: warm ochre for warm passages, cool grey-blue for cold.",
    "L6": f"The {PATHS} people with the most verified mentions (after name merging) have paths. A path touches "
          "the map in each passage that names them, in a lane of its own inside the band, so people who are "
          f"together run side by side. An absence of up to {GAP_MAX} passages is dotted; a longer one, or a move "
          "to another place, leaves a gap marked by small rings.",
    "L7": "Where the reader recorded an interaction between path characters, a meeting mark joins them.",
    "L8": "Objects the reader recorded are marked where they occur; letters and carriages get their own symbols.",
    "L9": "A place is lettered over each stretch of at least two passages set there.",
    "L10": "Where the story moves from one place to another between two passages, a dotted road joins the two bands.",
}


def _roman(n: int) -> str:
    out = ""
    for v, s in ((50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out, n = out + s, n - v
    return out


def _object_kind(name: str) -> str:
    n = name.lower()
    if re.search(r"\b(letter|note|epistle|express)\b", n):
        return "letter"
    if re.search(r"\b(carriage|chaise|coach|phaeton|post-chaise)\b", n):
        return "carriage"
    return "object"


def compose(run_dir: Path, book: Book, out_dir: Path | None = None, log=print) -> Path:
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "run.json").read_text())
    facts = [json.loads(l) for l in open(run_dir / "facts.jsonl")]
    settings = {r["passage"]: r for r in map(json.loads, open(run_dir / "settings" / "settings.jsonl"))}
    names = E.load(run_dir)  # name key -> entity
    by_id = {p.id: p for p in passages(book)}
    plist = [by_id[i] for i in manifest["passages"] if i in settings]
    N = len(plist)
    x0, x1 = MARGIN_X, SHEET_W - MARGIN_X
    dx = (x1 - x0) / max(1, N - 1)
    by_passage = defaultdict(list)
    for f in facts:
        by_passage[f["passage"]].append(f)

    # L2: where each passage stands.
    where, prev = [], None
    for p in plist:
        s = settings[p.id]["setting"]
        if s in ("unclear", "elsewhere"):
            where.append((prev or s, "carried"))
        else:
            where.append((s, "set"))
            prev = s
    # Passages before any setting is known take the first known one.
    first = next((w for w, how in where if how == "set"), "unclear")
    where = [(first, how) if w in ("unclear", "elsewhere") else (w, how) for w, how in where]

    # L3: bands in order of first visit, height by share of passages.
    order = list(dict.fromkeys(w for w, _ in where))
    count = Counter(w for w, _ in where)
    avail = SHEET_H - MARGIN_TOP - MARGIN_BOTTOM
    root = sum(count[b] ** 0.5 for b in order)
    raw = {b: max(BAND_MIN, avail * count[b] ** 0.5 / root) for b in order}
    scale = avail / sum(raw.values())
    bands, y = {}, MARGIN_TOP
    for b in order:
        h = raw[b] * scale
        bands[b] = {"name": b, "y": round(y + h / 2, 4), "h": round(h, 4), "passages": count[b]}
        y += h

    # Tone per passage (L4, L5).
    tone = {}
    for p in plist:
        t = next((f for f in by_passage[p.id] if f["type"] == "tone"), None)
        tone[p.id] = t

    out_passages = []
    for i, p in enumerate(plist):
        w, how = where[i]
        t = tone[p.id]
        s = settings[p.id]
        evs = [f for f in by_passage[p.id] if f["type"] == "event"]
        out_passages.append({
            "id": p.id, "chapter": p.chapter, "x": round(x0 + i * dx, 4), "band": w, "placed": how,
            "setting": {k: s.get(k) for k in ("setting", "basis", "rationale", "step", "flags", "spans", "call")},
            "tension": t["data"]["tension"] if t else None, "warmth": t["data"]["warmth"] if t else None,
            "tone": {"reason": t["data"]["reason"], "fact": t["id"], "spans": t["evidence"]["spans"]} if t else None,
            "events": [{"summary": e["data"]["summary"], "fact": e["id"], "spans": e["evidence"]["spans"]} for e in evs],
            "start": p.start, "end": p.end,
        })

    # L6: paths.
    mentions = Counter()
    entity_of = {}
    for f in facts:
        if f["type"] == "character":
            e = names.get(E.key(f["data"]["name"]))
            if e and e["kind"] == "person":
                mentions[e["id"]] += 1
                entity_of[f["id"]] = e
    walkers = [eid for eid, _ in mentions.most_common(PATHS)]
    canon = {e["id"]: e for e in names.values()}
    # Lanes: the most mentioned person in the middle, others alternating outwards.
    lanes = {}
    for k, eid in enumerate(walkers):
        lanes[eid] = (k + 1) // 2 * (1 if k % 2 else -1)
    span = max(abs(v) for v in lanes.values()) or 1
    paths = {eid: {"entity": eid, "name": canon[eid]["canonical"], "aliases": canon[eid]["names"],
                   "mentions": mentions[eid], "ink": INKS[k % len(INKS)], "lane": lanes[eid], "points": []}
             for k, eid in enumerate(walkers)}
    pos = {}  # (passage index, entity) -> (x, y)
    for i, p in enumerate(plist):
        seen = {}
        for f in by_passage[p.id]:
            e = entity_of.get(f["id"])
            if f["type"] == "character" and e and e["id"] in paths:
                seen.setdefault(e["id"], []).append(f)
        b = bands[where[i][0]]
        for eid, fs in seen.items():
            yy = b["y"] + lanes[eid] * min(LANE, b["h"] * 0.4 / span)
            pos[(i, eid)] = (out_passages[i]["x"], round(yy, 4))
            paths[eid]["points"].append({
                "i": i, "x": out_passages[i]["x"], "y": round(yy, 4), "passage": p.id,
                "called": sorted({f["data"]["called_here"] for f in fs}),
                "facts": [f["id"] for f in fs], "spans": [s for f in fs for s in f["evidence"]["spans"]]})

    # L7: meetings.
    meetings = []
    for i, p in enumerate(plist):
        for f in by_passage[p.id]:
            if f["type"] != "interaction":
                continue
            who = []
            for n in f["data"]["characters"]:
                e = names.get(E.key(n))
                if e and e["id"] in paths and (i, e["id"]) in pos and e["id"] not in who:
                    who.append(e["id"])
            if len(who) < 2:
                continue
            ys = [pos[(i, e)][1] for e in who]
            meetings.append({"x": out_passages[i]["x"], "y0": min(ys), "y1": max(ys), "who": who,
                             "kind": f["data"]["kind"], "summary": f["data"]["summary"], "passage": p.id,
                             "facts": [f["id"]], "spans": f["evidence"]["spans"], "rule": "L7"})

    # L8: objects.
    objects = []
    for i, p in enumerate(plist):
        b = bands[where[i][0]]
        k = 0
        for f in by_passage[p.id]:
            if f["type"] != "object":
                continue
            k += 1
            objects.append({"x": out_passages[i]["x"], "y": round(b["y"] - b["h"] * 0.46 + 0.18 * k, 4),
                            "name": f["data"]["name"], "kind": _object_kind(f["data"]["name"]),
                            "description": f["data"].get("description"), "passage": p.id,
                            "facts": [f["id"]], "spans": f["evidence"]["spans"], "rule": "L8"})

    # L10: roads where the scene moves.
    roads = []
    for i in range(1, N):
        a, b = where[i - 1][0], where[i][0]
        if a != b:
            roads.append({"x0": out_passages[i - 1]["x"], "y0": bands[a]["y"], "x1": out_passages[i]["x"],
                          "y1": bands[b]["y"], "from": a, "to": b,
                          "passages": [plist[i - 1].id, plist[i].id], "rule": "L10"})

    # L9: place lettering over runs.
    labels, run_start = [], 0
    for i in range(1, N + 1):
        if i == N or where[i][0] != where[run_start][0]:
            if i - run_start >= 2:
                xa, xb = out_passages[run_start]["x"], out_passages[i - 1]["x"]
                labels.append({"text": where[run_start][0], "x": round((xa + xb) / 2, 4),
                               "y": bands[where[run_start][0]]["y"], "width": round(xb - xa, 4),
                               "passages": [out_passages[j]["id"] for j in range(run_start, i)], "rule": "L9"})
            run_start = i

    chapters = []
    for c in sorted({p.chapter for p in plist}):
        xs = [q["x"] for q in out_passages if q["chapter"] == c]
        chapters.append({"n": c, "label": _roman(c), "x0": min(xs) - dx / 2, "x1": max(xs) + dx / 2})

    layout = {
        "book": {"title": book.title, "author": book.author, "slug": book.slug, "sha256": book.sha256},
        "run": {"id": manifest["run_id"], "model": manifest["backend"]["model"],
                "digest": manifest["backend"].get("digest"), "prompt": manifest["prompt_version"],
                "checker": manifest.get("checker", 1)},
        "generated": datetime.now(timezone.utc).isoformat(),
        "sheet": {"w": SHEET_W, "h": SHEET_H, "x0": x0, "x1": x1, "dx": dx,
                  "top": MARGIN_TOP, "bottom": SHEET_H - MARGIN_BOTTOM},
        "gap_max": GAP_MAX,
        "terrain": {"floor": RIDGE_FLOOR, "sigma_x": SIGMA_X * dx, "sigma_y": SIGMA_Y},
        "rules": RULES,
        "bands": list(bands.values()),
        "passages": out_passages,
        "paths": [v for v in paths.values() if v["points"]],
        "meetings": meetings,
        "objects": objects,
        "roads": roads,
        "labels": labels,
        "chapters": chapters,
    }
    out = Path(out_dir or ROOT / "site" / "data" / book.slug)
    out.mkdir(parents=True, exist_ok=True)
    (out / "layout.json").write_text(json.dumps(layout, ensure_ascii=False))
    # The text itself, so every mark can be read against its passage. Public domain.
    text = {"file": manifest["book"]["file"], "sha256": book.sha256,
            "passages": {p.id: book.text[p.start:p.end] for p in plist}}
    (out / "text.json").write_text(json.dumps(text, ensure_ascii=False))
    log(f"{N} passages, {len(bands)} bands, {len(paths)} paths, {len(meetings)} meetings, "
        f"{len(objects)} objects, {len(labels)} labels -> {out}")
    return out
