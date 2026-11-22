"""How far to trust the sentence labels: four checks, all counted, none needing a model.

  stability   the first reading against the second (same question, other words):
              how many sentences keep their label, and how many rows keep their yarn
  memory      the first reading against itself with every name swapped for a neutral
              one. Only meaningful beside stability: both change the words the model
              sees without changing what the sentence means, so if swapping names moves
              labels much more than rewording the question does, the names mattered
  other       the first reading against the same question put to a different model.
              Two models agreeing is not proof either is right, but it is a check that
              does not depend on the main reader
  hand        a person's blind labels of a fixed random sample against each reading
  spread      how often each label and each yarn is used

Agreement is reported with Cohen's kappa as well, because two labellers who both say
"calm" most of the time agree often by chance alone. Writes checks.json for the site.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import knit as K
from . import labels as LB
from .source import ROOT

FEEL, PACE = {"neither": 0, "warm": 1, "cold": 2}, {"calm": 0, "tense": 1}


def agreement(pairs: list[tuple[int, int]]) -> dict | None:
    """Share of pairs that match, and Cohen's kappa (agreement beyond chance; 0 chance, 1 perfect)."""
    n = len(pairs)
    if not n:
        return None
    same = sum(a == b for a, b in pairs) / n
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    chance = sum(left[v] * right[v] for v in left) / (n * n)
    return {"n": n, "same": round(same, 6), "kappa": round((same - chance) / (1 - chance), 4) if chance < 1 else 1.0,
            "table": {f"{a}>{b}": c for (a, b), c in sorted(Counter(pairs).items())}}


def _sentences(x: dict, y: dict, key: str, code: dict) -> list[tuple[int, int]]:
    return [(code[a], code[b]) for pid in x if pid in y and x[pid]["n"] == y[pid]["n"]
            for a, b in zip(x[pid][key], y[pid][key])]


def _rows(x: dict, y: dict) -> dict | None:
    """Compare what rule K2 and K3 would make of each passage under two readings."""
    yarn, ridge = [], []
    for pid in x:
        if pid not in y or x[pid]["n"] != y[pid]["n"]:
            continue
        tx = K.tally([FEEL[f] for f in x[pid]["feeling"]], [PACE[p] for p in x[pid]["pace"]])
        ty = K.tally([FEEL[f] for f in y[pid]["feeling"]], [PACE[p] for p in y[pid]["pace"]])
        yarn.append(("ABCDE".index(tx["yarn"]), "ABCDE".index(ty["yarn"])))
        ridge.append((int(tx["ridged"]), int(ty["ridged"])))
    if not yarn:
        return None
    return {"yarn": agreement(yarn), "ridge": agreement(ridge),
            "yarn_within_one": round(sum(abs(a - b) <= 1 for a, b in yarn) / len(yarn), 6)}


def compare(x: dict, y: dict) -> dict | None:
    if not x or not y:
        return None
    return {"passages": len(set(x) & set(y)), "feeling": agreement(_sentences(x, y, "feeling", FEEL)),
            "pace": agreement(_sentences(x, y, "pace", PACE)), "rows": _rows(x, y)}


def check(run_dir: Path, book_json: Path, hand: Path | None = None, out_dir: Path | None = None, log=print) -> Path:
    run_dir = Path(run_dir)
    B = json.loads(Path(book_json).read_text())
    a, b, sw = LB.load(run_dir, "a"), LB.load(run_dir, "b"), LB.load(run_dir, "a-swapped")
    doc = {"book": B["book"], "run": B["run"], "generated": datetime.now(timezone.utc).isoformat(),
           "readings": {"a": len(a), "b": len(b), "a-swapped": len(sw)},
           "spread": {name: {"feeling": dict(Counter(f for r in got.values() for f in r["feeling"])),
                             "pace": dict(Counter(f for r in got.values() for f in r["pace"]))}
                      for name, got in (("a", a), ("b", b), ("a-swapped", sw)) if got},
           "stability": compare(a, b), "memory": compare(a, sw), "other": {}, "hand": None}
    for d in sorted((run_dir / "labels").glob("a-*")):
        if d.name == "a-swapped" or not (d / "run.json").exists():
            continue
        got = LB.load(run_dir, d.name)
        if got:
            doc["other"][d.name[2:]] = {"model": json.loads((d / "run.json").read_text())["backend"]["model"],
                                        "of": len(a), **compare(a, got)}
    if hand and Path(hand).exists():
        H = json.loads(Path(hand).read_text())
        S = B["sentences"]
        if H.get("run") != B["run"]["id"]:
            raise ValueError("these hand labels were made against a different run")
        mine = [h for h in H["labels"] if S["start"][h["sentence"]] == h["start"]]
        doc["hand"] = {"sentences": len(mine), "seed": H.get("seed"), "saved": H.get("saved")}
        for name, fcol, pcol in (("a", "feeling", "pace"), ("b", "feeling_b", "pace_b")):
            doc["hand"][name] = {
                "feeling": agreement([(FEEL[h["feeling"]], S[fcol][h["sentence"]]) for h in mine if S[fcol][h["sentence"]] >= 0]),
                "pace": agreement([(PACE[h["pace"]], S[pcol][h["sentence"]]) for h in mine if S[pcol][h["sentence"]] >= 0])}
    out = Path(out_dir or ROOT / "site" / "data" / B["book"]["slug"])
    (out / "checks.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))

    def line(name, c):
        if c:
            r = c["rows"]
            log(f"{name}: feeling same {c['feeling']['same']:.0%} (kappa {c['feeling']['kappa']:.2f}), pace same "
                f"{c['pace']['same']:.0%} (kappa {c['pace']['kappa']:.2f}); rows: same yarn {r['yarn']['same']:.0%}, "
                f"within one yarn {r['yarn_within_one']:.0%}, same texture {r['ridge']['same']:.0%} "
                f"({c['passages']} passages)")
    line("stability (a vs b)", doc["stability"])
    line("memory (a vs a with names swapped)", doc["memory"])
    for tag, c in doc["other"].items():
        line(f"other model (a vs {c['model']})", c)
    if doc["hand"]:
        for name in ("a", "b"):
            h = doc["hand"][name]
            log(f"hand vs {name}: feeling same {h['feeling']['same']:.0%} (kappa {h['feeling']['kappa']:.2f}), pace same "
                f"{h['pace']['same']:.0%} (kappa {h['pace']['kappa']:.2f}) on {h['feeling']['n']} sentences")
    else:
        log("hand: no hand labels yet (label them at site/knit/check.html, save to data/handcheck.json)")
    return out
