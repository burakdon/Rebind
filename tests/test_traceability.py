"""The guarantees the rest of Rebind relies on."""

import re

import pytest

from rebind import source
from rebind.verify import find_quote


@pytest.fixture(scope="module")
def book():
    return source.load_book("pride-and-prejudice")


@pytest.fixture(scope="module")
def plist(book):
    return source.passages(book)


def test_all_chapters_found(book):
    assert [c.number for c in source.chapters(book)] == list(range(1, 62))


def test_passages_are_ordered_disjoint_windows_on_the_source(book, plist):
    body = source.body_span(book)
    prev_end = body.start
    for p in plist:
        assert prev_end <= p.start < p.end <= body.end
        for para in p.paragraphs:
            assert p.start <= para.start < para.end <= p.end
        prev_end = p.end


def test_no_excluded_text_inside_passages(book, plist):
    holes = [s for s, _ in source.excluded_spans(book)]
    for p in plist:
        for para in p.paragraphs:
            assert not any(h.start < para.end and para.start < h.end for h in holes), p.id


def test_first_line(book, plist):
    assert plist[0].display_text(book).startswith("It is a truth universally acknowledged")


def _passage(plist, pid):
    return next(p for p in plist if p.id == pid)


def test_quote_with_restyled_punctuation_matches(book, plist):
    p = _passage(plist, "c01.p01")
    m = find_quote(book.text, p.start, p.end, '"My dear Mr. Bennet," said his lady to him one day')
    assert m is not None
    a, b = m.spans[0]
    assert book.text[a:b].startswith("My dear Mr. Bennet")


def test_italic_markers_and_line_breaks_are_ignored(book, plist):
    p = _passage(plist, "c01.p01")
    # Source has “_You_ want to tell me” across Gutenberg italics markers.
    assert find_quote(book.text, p.start, p.end, "You want to tell me, and I have no objection to hearing it")


def test_paraphrase_is_rejected(book, plist):
    p = _passage(plist, "c01.p01")
    assert find_quote(book.text, p.start, p.end, "a rich single man must want a wife") is None


def test_quote_from_another_passage_is_rejected(book, plist):
    p = _passage(plist, "c02.p01")
    assert find_quote(book.text, p.start, p.end, "It is a truth universally acknowledged") is None


def test_ellipsis_fragments_must_appear_in_order(book, plist):
    p = _passage(plist, "c01.p01")
    assert find_quote(book.text, p.start, p.end, "It is a truth ... must be in want of a wife")
    assert find_quote(book.text, p.start, p.end, "must be in want of a wife ... It is a truth") is None


def test_no_partial_word_matches(book, plist):
    p = _passage(plist, "c01.p01")
    assert find_quote(book.text, p.start, p.end, "ruth universally") is None


def test_support_check_needs_the_name():
    from rebind.verify import mentions
    assert mentions("“My dear Mr. Bennet,” said his lady", "Mrs. Bennet")
    assert mentions("Mr. Bingley’s large fortune", "Charles Bingley")
    assert not mentions("It is a truth universally acknowledged", "Mrs. Bennet")
    assert not mentions("said Mrs. Long", "Mrs. Bennet")  # a title alone is not a name


def test_a_pronoun_is_not_evidence_for_a_character(book, plist):
    from rebind import extract
    p = _passage(plist, "c01.p01")
    _, sents = p.numbered_text(book)
    i = 1  # the pronoun rule refuses before looking at the sentence
    for called in ("her", "you", "the others"):
        r = extract.check(book, p, sents, "character", {"name": "Mrs. Bennet", "called_here": called}, [i], "c")
        assert (r["status"], r["support"]) == ("rejected", "pronoun only")
    r = extract.check(book, p, sents, "character", {"name": "Mrs. Bennet", "called_here": "his lady"}, [i], "c")
    assert r["support"] != "pronoun only"  # a description is still checked as words


def test_called_here_must_be_whole_words():
    from rebind.verify import says
    assert says("“My dear Mr. Bennet,” said his lady", "his lady")
    assert not says("there was nothing", "her")
    assert not says("Janet came in", "Jane")
