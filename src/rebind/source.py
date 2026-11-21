"""Load a book exactly as published and cut it into passages.

Every span here is a pair of character offsets into the source file, decoded
as UTF-8 with no newline translation. Nothing is rewritten: a passage is only
a window onto the original text, so any citation can be checked by slicing
the file.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

START_RE = re.compile(r"\*\*\* START OF TH(?:E|IS) PROJECT GUTENBERG EBOOK[^\n]*\n")
END_RE = re.compile(r"\*\*\* END OF TH(?:E|IS) PROJECT GUTENBERG EBOOK")
BLANK_LINES_RE = re.compile(r"(?:\r?\n)[ \t]*(?:\r?\n)+")
WORD_RE = re.compile(r"[A-Za-z’']+")


@dataclass
class Book:
    slug: str
    title: str
    author: str
    path: Path
    text: str
    sha256: str
    config: dict


@dataclass
class Span:
    start: int
    end: int


@dataclass
class Chapter:
    number: int
    heading: str
    start: int
    end: int


@dataclass
class Passage:
    id: str
    chapter: int
    index: int
    start: int
    end: int
    paragraphs: list[Span] = field(default_factory=list)
    n_words: int = 0

    def display_text(self, book: Book) -> str:
        """The passage as a reader sees it: paragraphs joined, line breaks unwrapped."""
        return "\n\n".join(_unwrap(book.text[p.start : p.end]) for p in self.paragraphs)

    def sentences(self, book: Book) -> list[list[Span]]:
        """Sentences of each paragraph, as exact spans in the source."""
        return [sentence_spans(book.text, para) for para in self.paragraphs]

    def numbered_text(self, book: Book) -> tuple[str, list[Span]]:
        """The passage with every sentence numbered [1], [2], ... and the span of each number."""
        flat: list[Span] = []
        paras = []
        for sents in self.sentences(book):
            parts = []
            for s in sents:
                flat.append(s)
                parts.append(f"[{len(flat)}] {_unwrap(book.text[s.start:s.end])}")
            paras.append(" ".join(parts))
        return "\n\n".join(paras), flat

    def to_json(self, book: Book) -> dict:
        return {
            "id": self.id,
            "chapter": self.chapter,
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "n_words": self.n_words,
            "paragraphs": [[p.start, p.end] for p in self.paragraphs],
            "text": self.display_text(book),
        }


def load_book(slug: str) -> Book:
    cfg = json.loads((ROOT / "books" / f"{slug}.json").read_text())
    path = ROOT / cfg["file"]
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != cfg["sha256"]:
        raise ValueError(
            f"{path} has sha256 {sha}, expected {cfg['sha256']}. "
            "Offsets would not match the published edition; re-download or update the config."
        )
    return Book(
        slug=cfg["slug"],
        title=cfg["title"],
        author=cfg["author"],
        path=path,
        text=raw.decode("utf-8"),
        sha256=sha,
        config=cfg,
    )


def roman_to_int(s: str) -> int:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for a, b in zip(s, s[1:] + " "):
        v = values[a]
        total += -v if b != " " and values.get(b, 0) > v else v
    return total


def body_span(book: Book) -> Span:
    m_start = START_RE.search(book.text)
    m_end = END_RE.search(book.text)
    if not m_start or not m_end:
        raise ValueError("Project Gutenberg START/END markers not found")
    return Span(m_start.end(), m_end.start())


def bracket_blocks(text: str, opener: str, lo: int, hi: int) -> list[Span]:
    """Spans of `[Illustration ...]` blocks, honouring nested brackets."""
    spans = []
    i = text.find(opener, lo, hi)
    while i != -1:
        depth, j = 0, i
        while j < hi:
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        spans.append(Span(i, j + 1))
        i = text.find(opener, j + 1, hi)
    return spans


def excluded_spans(book: Book) -> list[tuple[Span, str]]:
    body = body_span(book)
    out = [
        (s, "Illustration caption or plate from the 1894 edition")
        for s in bracket_blocks(book.text, "[Illustration", body.start, body.end)
    ]
    for rule in book.config.get("exclude", []):
        for m in re.compile(rule["pattern"], re.S).finditer(book.text, body.start, body.end):
            out.append((Span(m.start(), m.end()), rule["why"]))
    return sorted(out, key=lambda t: t[0].start)


def chapters(book: Book) -> list[Chapter]:
    body = body_span(book)
    pat = re.compile(book.config["chapter_pattern"], re.M)
    heads = list(pat.finditer(book.text, body.start, body.end))
    out = []
    for k, m in enumerate(heads):
        end = heads[k + 1].start() if k + 1 < len(heads) else body.end
        out.append(Chapter(roman_to_int(m.group(1)), m.group(0).strip(), m.end(), end))
    return out


def _subtract(span: Span, holes: list[Span]) -> list[Span]:
    pieces, cur = [], span.start
    for h in holes:
        if h.end <= cur or h.start >= span.end:
            continue
        if h.start > cur:
            pieces.append(Span(cur, h.start))
        cur = max(cur, h.end)
    if cur < span.end:
        pieces.append(Span(cur, span.end))
    return pieces


def _strip(text: str, s: Span) -> Span | None:
    a, b = s.start, s.end
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    return Span(a, b) if b > a else None


def paragraphs(book: Book, ch: Chapter, holes: list[Span]) -> list[Span]:
    out = []
    for piece in _subtract(Span(ch.start, ch.end), holes):
        cur = piece.start
        for m in BLANK_LINES_RE.finditer(book.text, piece.start, piece.end):
            if (s := _strip(book.text, Span(cur, m.start()))):
                out.append(s)
            cur = m.end()
        if (s := _strip(book.text, Span(cur, piece.end))):
            out.append(s)
    return out


SENTENCE_END_RE = re.compile(r"[.?!][”’\"')]*\s+(?=[“‘\"'(_]?[A-Z])")
# Abbreviations that end in a full stop but do not end a sentence.
ABBREV_RE = re.compile(r"(?:\b(?:Mr|Mrs|Dr|St|Messrs|Col|Capt)|\b[A-Z])\.$")


def _unwrap(s: str) -> str:
    return re.sub(r"\s*\r?\n\s*", " ", s)


def sentence_spans(text: str, para: Span) -> list[Span]:
    out, cur = [], para.start
    for m in SENTENCE_END_RE.finditer(text, para.start, para.end):
        end = m.end()
        if ABBREV_RE.search(text[max(para.start, m.start() - 8) : m.start() + 1]):
            continue
        if (s := _strip(text, Span(cur, end))):
            out.append(s)
        cur = end
    if (s := _strip(text, Span(cur, para.end))):
        out.append(s)
    return out


def split_long(text: str, p: Span, max_words: int) -> list[Span]:
    """Cut an over-long paragraph (Darcy's letter is one 2,000-word paragraph in
    this edition) at sentence ends into pieces of at most ~max_words."""
    n = len(WORD_RE.findall(text[p.start : p.end]))
    if n <= max_words:
        return [p]
    pieces = -(-n // max_words)
    goal = n / pieces
    out, cur, words = [], p.start, 0
    last = p.start
    for m in SENTENCE_END_RE.finditer(text, p.start, p.end):
        words += len(WORD_RE.findall(text[last : m.end()]))
        last = m.end()
        if words >= goal and len(out) < pieces - 1:
            out.append(Span(cur, m.start() + 1))
            cur, words = m.end(), 0
    out.append(Span(cur, p.end))
    return [s for s in (_strip(text, x) for x in out) if s]


def passages(book: Book, target_words: int | None = None, max_words: int | None = None) -> list[Passage]:
    """Group whole paragraphs into passages of roughly `target_words`.

    Paragraphs are split only when one alone exceeds `max_words`, and then at
    a sentence end, so every boundary is a natural break in the original. The
    sizes come from the book's config (350 and 650 words unless it says otherwise):
    a short book is cut finer so it still makes a scarf of a wearable length.
    """
    target_words = target_words or book.config.get("passage_words", 350)
    max_words = max_words or book.config.get("passage_max_words", 650)
    holes = [s for s, _ in excluded_spans(book)]
    out: list[Passage] = []
    for ch in chapters(book):
        group: list[Span] = []
        words = 0
        k = 0

        def flush():
            nonlocal group, words, k
            if group:
                k += 1
                out.append(
                    Passage(
                        id=f"c{ch.number:02d}.p{k:02d}",
                        chapter=ch.number,
                        index=k,
                        start=group[0].start,
                        end=group[-1].end,
                        paragraphs=group,
                        n_words=words,
                    )
                )
            group, words = [], 0

        units = [s for para in paragraphs(book, ch, holes) for s in split_long(book.text, para, max_words)]
        for p in units:
            n = len(WORD_RE.findall(book.text[p.start : p.end]))
            if group and words + n > max_words:
                flush()
            group.append(p)
            words += n
            if words >= target_words:
                flush()
        # Fold a short tail into the previous passage of the same chapter.
        if group and out and out[-1].chapter == ch.number and words < target_words // 3:
            prev = out[-1]
            prev.paragraphs.extend(group)
            prev.end = group[-1].end
            prev.n_words += words
            group, words = [], 0
        flush()
    return out
