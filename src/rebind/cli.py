"""Command line: segment, read, trace, summary, recheck, resolve, locate, compose, compare."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from . import compose, entities, extract, setting, source
from .backends import from_spec


def parse_chapters(s: str | None) -> set[int] | None:
    if not s:
        return None
    out: set[int] = set()
    for part in s.split(","):
        a, _, b = part.partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return out


def cmd_segment(args):
    book = source.load_book(args.book)
    out = source.ROOT / "out" / book.slug
    out.mkdir(parents=True, exist_ok=True)
    ps = source.passages(book)
    with open(out / "passages.jsonl", "w") as f:
        for p in ps:
            f.write(json.dumps(p.to_json(book), ensure_ascii=False) + "\n")
    with open(out / "excluded.jsonl", "w") as f:
        for s, why in source.excluded_spans(book):
            f.write(json.dumps({"start": s.start, "end": s.end, "why": why,
                                "text": book.text[s.start:s.end]}, ensure_ascii=False) + "\n")
    chs = source.chapters(book)
    words = [p.n_words for p in ps]
    print(f"{book.title}: {len(chs)} chapters, {len(ps)} passages, {sum(words):,} words "
          f"(passage length {min(words)}–{max(words)}, median {sorted(words)[len(words)//2]})")
    print(f"wrote {out/'passages.jsonl'} and {out/'excluded.jsonl'}")


def cmd_read(args):
    if args.resume:
        # Everything comes from the stopped run, so nothing can be resumed with different settings.
        m = json.loads((Path(args.resume) / "run.json").read_text())
        book = source.load_book(m["book"]["slug"])
        by_id = {p.id: p for p in source.passages(book)}
        ps = [by_id[i] for i in m["passages"]]
        backend = from_spec(m["backend"]["spec"])
    else:
        book = source.load_book(args.book)
        chs = parse_chapters(args.chapters)
        ps = [p for p in source.passages(book) if chs is None or p.chapter in chs]
        if args.limit:
            ps = ps[: args.limit]
        backend = from_spec(args.model)
    print(f"reading {len(ps)} passages of {book.title} with {backend.spec} (prompt {extract.prompt_version()})",
          flush=True)
    out = extract.run(book, ps, backend, resume=args.resume, log=lambda s: print(s, flush=True))
    m = json.loads((out / "run.json").read_text())
    print(f"\nrun written to {out}")
    print(json.dumps(m["counts"], indent=2))


def cmd_trace(args):
    """Show a fact next to the exact characters it cites in the source file."""
    book = source.load_book(args.book)
    for path in Path(args.run).glob("facts.jsonl"):
        for line in open(path):
            r = json.loads(line)
            if r["id"] == args.fact:
                print(json.dumps({k: r[k] for k in ("id", "type", "passage", "data")}, indent=2, ensure_ascii=False))
                for a, b in r["evidence"]["spans"]:
                    lo, hi = max(0, a - 160), min(len(book.text), b + 160)
                    ctx = book.text[lo:a] + "\033[1;33m" + book.text[a:b] + "\033[0m" + book.text[b:hi]
                    print(f"\n{book.path.name} [{a}:{b}] sha256 {book.sha256[:12]}…\n")
                    print(ctx.replace("\r\n", "\n"))
                return
    raise SystemExit(f"fact {args.fact} not found in {args.run}")


def cmd_summary(args):
    run = Path(args.run)
    m = json.loads((run / "run.json").read_text())
    facts = [json.loads(l) for l in open(run / "facts.jsonl")]
    rej = [json.loads(l) for l in open(run / "rejected.jsonl")]
    print(f"run {m['run_id']}  model {m['backend']['model']}  prompt {m['prompt_version']}")
    print(f"{len(facts)} verified, {len(rej)} rejected "
          f"({len(rej) / max(1, len(facts) + len(rej)):.0%} rejection rate)")
    print("by type:", dict(Counter(f["type"] for f in facts)))
    print("rejections:", dict(Counter(r.get("reason") for r in rej)))
    print("cast:", m.get("cast"))


def _reason_kind(reason: str) -> str:
    for key in ("no evidence", "no such sentence", "only a pronoun", "does not name", "schema"):
        if key in reason:
            return key
    return "other"


def cmd_compare(args):
    """Runs side by side: what each model got verified, what was refused and why, and speed."""
    rows = []
    for path in args.runs:
        run = Path(path)
        m = json.loads((run / "run.json").read_text())
        facts = [json.loads(l) for l in open(run / "facts.jsonl")]
        rej = [json.loads(l) for l in open(run / "rejected.jsonl")]
        calls = [json.loads(l) for l in open(run / "calls.jsonl")]
        n_pass = len({c["passage"] for c in calls}) or 1
        types = Counter(f["type"] for f in facts)
        rows.append({
            "model": m["backend"]["model"],
            "size": m["backend"].get("parameter_size") or "?",
            "prompt": m["prompt_version"],
            "verified": len(facts),
            "rejected": len(rej),
            "reject %": f"{len(rej) / max(1, len(facts) + len(rej)):.0%}",
            **{t: types.get(t, 0) for t in ("character", "interaction", "place", "object", "event", "tone")},
            "names": len({f["data"]["name"] for f in facts if f["type"] == "character"}),
            **{f"rej: {k}": v for k, v in Counter(_reason_kind(r.get("reason", "")) for r in rej).items()},
            "calls": len(calls),
            "hit token limit": sum(c.get("finish_reason") == "length" for c in calls),
            "call errors": sum(bool(c.get("error")) for c in calls),
            "median s/call": sorted(c.get("latency_s", 0) for c in calls)[len(calls) // 2] if calls else 0,
            "s/passage": round(sum(c.get("latency_s", 0) for c in calls) / n_pass),
        })
    keys = list(dict.fromkeys(k for r in rows for k in r))
    width = max(len(k) for k in keys)
    for k in keys:
        print(f"{k:<{width}}  " + "  ".join(f"{str(r.get(k, 0)):>22}" for r in rows))


def cmd_recheck(args):
    m = json.loads((Path(args.run) / "run.json").read_text())
    extract.recheck(Path(args.run), source.load_book(m["book"]["slug"]))


def cmd_locate(args):
    run = Path(args.run)
    m = json.loads((run / "run.json").read_text())
    out = setting.locate(run, source.load_book(m["book"]["slug"]), from_spec(args.model or m["backend"]["spec"]),
                         log=lambda s: print(s, flush=True))
    print(json.dumps(json.loads((out / "run.json").read_text())["counts"], indent=2))


def cmd_compose(args):
    run = Path(args.run)
    m = json.loads((run / "run.json").read_text())
    compose.compose(run, source.load_book(m["book"]["slug"]))


def cmd_resolve(args):
    run = Path(args.run)
    spec = args.model or json.loads((run / "run.json").read_text())["backend"]["spec"]
    out = entities.resolve(run, from_spec(spec), log=lambda s: print(s, flush=True))
    table = json.loads((out / "entities.json").read_text())
    print(f"\nwritten to {out}")
    print(json.dumps(json.loads((out / "run.json").read_text())["counts"], indent=2))
    for t in table[:25]:
        print(f"{t['mentions']:5}  {t['kind']:<13} {t['canonical']:<28} {t['names'][1:6]}")


def main():
    ap = argparse.ArgumentParser(prog="rebind")
    sub = ap.add_subparsers(required=True)
    s = sub.add_parser("segment", help="cut the book into passages with source offsets")
    s.add_argument("--book", default="pride-and-prejudice")
    s.set_defaults(fn=cmd_segment)
    r = sub.add_parser("read", help="extract cited facts with a reader model")
    r.add_argument("--book", default="pride-and-prejudice")
    r.add_argument("--model", default="ollama:olmo-3:7b-instruct")
    r.add_argument("--chapters", help="e.g. 1-3 or 1,34,58")
    r.add_argument("--limit", type=int)
    r.add_argument("--resume", metavar="RUN_DIR", help="continue a stopped run where it left off")
    r.set_defaults(fn=cmd_read)
    t = sub.add_parser("trace", help="show a fact against the source text")
    t.add_argument("run")
    t.add_argument("fact")
    t.add_argument("--book", default="pride-and-prejudice")
    t.set_defaults(fn=cmd_trace)
    m = sub.add_parser("summary", help="counts and rejection rate for a run")
    m.add_argument("run")
    m.set_defaults(fn=cmd_summary)
    k = sub.add_parser("recheck", help="apply the current checker to an older run (no model needed)")
    k.add_argument("run")
    k.set_defaults(fn=cmd_recheck)
    e = sub.add_parser("resolve", help="merge character names into entities")
    e.add_argument("run")
    e.add_argument("--model", help="defaults to the model that did the reading")
    e.set_defaults(fn=cmd_resolve)
    lo = sub.add_parser("locate", help="decide where each passage takes place")
    lo.add_argument("run")
    lo.add_argument("--model", help="defaults to the model that did the reading")
    lo.set_defaults(fn=cmd_locate)
    co = sub.add_parser("compose", help="lay the reading out as a map for the site")
    co.add_argument("run")
    co.set_defaults(fn=cmd_compose)
    c = sub.add_parser("compare", help="several runs side by side")
    c.add_argument("runs", nargs="+")
    c.set_defaults(fn=cmd_compare)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
