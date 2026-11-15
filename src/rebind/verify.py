"""Check that a quoted string really occurs in the source, and find where.

Models restyle punctuation (straight vs curly quotes, `--` vs an em dash),
drop Gutenberg's `_italic_` underscores and re-wrap lines. None of that
changes the words, so matching runs on a normalised copy of the text that
keeps a map from every normalised character back to its offset in the
original file. Anything beyond these surface differences is a mismatch and
the quote is rejected.
"""

from __future__ import annotations

from dataclasses import dataclass

_TRANSLATE = {
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"', "«": '"', "»": '"',
    # Single and double quotation marks are folded together: models often close
    # dialogue with ’ where the edition has ”. Apostrophes fold the same way on
    # both sides, so words like "don't" still match.
    "‘": '"', "’": '"', "‚": '"', "‛": '"', "′": '"', "`": '"', "'": '"',
    "–": "-", "—": "-", "―": "-", "‐": "-", "‑": "-",
}
ELLIPSES = ("...", "…", ". . .")
MIN_FRAGMENT_CHARS = 4


@dataclass
class Normalised:
    text: str
    to_source: list[int]  # to_source[i] = offset in the original of normalised char i


def normalise(source: str, start: int = 0, end: int | None = None) -> Normalised:
    end = len(source) if end is None else end
    out: list[str] = []
    idx: list[int] = []
    prev_space = True
    prev_dash = False
    for i in range(start, end):
        ch = source[i]
        if ch == "_":
            continue
        ch = _TRANSLATE.get(ch, ch)
        if ch.isspace():
            if not prev_space:
                out.append(" ")
                idx.append(i)
            prev_space, prev_dash = True, False
            continue
        if ch == "-":
            if prev_dash:
                continue
            prev_dash = True
        else:
            prev_dash = False
        out.append(ch.lower()[0])
        idx.append(i)
        prev_space = False
    if out and out[-1] == " ":
        out.pop()
        idx.pop()
    return Normalised("".join(out), idx)


def _clean_fragment(q: str) -> str:
    n = normalise(q).text
    return n.strip(" \"'.,;:!?-")


@dataclass
class Match:
    spans: list[tuple[int, int]]  # [start, end) offsets in the original file
    occurrences: int  # how often the first fragment appears in the passage


def find_quote(source: str, start: int, end: int, quote: str, hay: Normalised | None = None) -> Match | None:
    """Locate `quote` inside source[start:end]. Ellipses split it into fragments
    that must appear in order. Returns None if any fragment is missing."""
    hay = hay or normalise(source, start, end)
    q = quote
    for e in ELLIPSES[1:]:
        q = q.replace(e, ELLIPSES[0])
    fragments = [f for f in (_clean_fragment(x) for x in q.split(ELLIPSES[0])) if f]
    if not fragments or any(len(f) < MIN_FRAGMENT_CHARS for f in fragments):
        return None
    spans = []
    pos = 0
    occurrences = len(_find_all(hay.text, fragments[0], 0))
    for f in fragments:
        hits = _find_all(hay.text, f, pos, first_only=True)
        if not hits:
            return None
        i = hits[0]
        j = i + len(f)
        spans.append((hay.to_source[i], hay.to_source[j - 1] + 1))
        pos = j
    return Match(spans, occurrences)


TITLES = {"mr", "mrs", "miss", "lady", "sir", "lord", "dr", "colonel", "captain", "the", "of", "and"}


def name_tokens(name: str) -> set[str]:
    words = {w.strip(".,'\"") for w in normalise(name).text.replace('"', " ").split()}
    return {w for w in words if w and w not in TITLES and len(w) > 2}


def mentions(quote_source_text: str, name: str) -> bool:
    """Does the cited text name this entity? Any distinctive word of the name
    counts ("Bennet" supports "Mrs. Bennet"); titles alone do not."""
    hay = set(normalise(quote_source_text).text.replace('"', " ").replace("-", " ").split())
    hay = {w.strip(".,;:!?()") for w in hay}
    toks = name_tokens(name)
    return bool(toks) and any(t in hay or t.rstrip("s") in hay for t in toks)


def _find_all(text: str, frag: str, pos: int, first_only: bool = False) -> list[int]:
    """Occurrences of `frag` that start and end on word boundaries."""
    hits = []
    i = text.find(frag, pos)
    while i != -1:
        j = i + len(frag)
        before_ok = i == 0 or not text[i - 1].isalnum() or not frag[0].isalnum()
        after_ok = j == len(text) or not text[j].isalnum() or not frag[-1].isalnum()
        if before_ok and after_ok:
            hits.append(i)
            if first_only:
                break
        i = text.find(frag, i + 1)
    return hits


# Words that can stand for anyone. A `called_here` made only of these ("her", "you",
# "the others") is present in almost every sentence, so finding it proves nothing
# about who the sentence is about.
REFERRING_WORDS = {
    "i", "me", "my", "mine", "myself", "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself", "it", "its", "itself",
    "we", "us", "our", "ours", "ourselves", "they", "them", "their", "theirs", "themselves",
    "who", "whom", "whose", "which", "this", "that", "these", "those", "the", "a", "an",
    "one", "ones", "other", "others", "another", "both", "all", "each", "some", "any", "own",
}


def only_referring_words(phrase: str) -> bool:
    words = [w.strip(".,;:!?()\"-") for w in normalise(phrase).text.split()]
    return all(w in REFERRING_WORDS for w in words if w)


def says(text: str, phrase: str) -> bool:
    """Does `phrase` occur in `text` as whole words (so "her" is not found in "there")?"""
    frag = normalise(phrase).text.strip(' "')
    return len(frag) >= 2 and bool(_find_all(normalise(text).text, frag, 0, first_only=True))
