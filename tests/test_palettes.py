"""The dye: every book names a palette that exists, and no two yarns of a palette can be mistaken for each other.

Colour difference is distance in OKLab x 100. Red-green colour blindness is simulated with the matrices of
Machado, Oliveira and Fernandes (2009) at full severity, in linear RGB. The floors (15 with full colour
vision, 8 with either kind of red-green colour blindness) are ordinary ones for colours that must be told apart.
"""

import json
from itertools import combinations

from rebind import knit
from rebind.source import ROOT

MACHADO = {
    "protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
}


def linear(hx):
    c = [int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]


def oklab(rgb):
    r, g, b = rgb
    l, m, s = (x ** (1 / 3) for x in (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
                                      0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
                                      0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def seen(hx, kind=None):
    rgb = linear(hx)
    if kind:
        rgb = [min(1, max(0, sum(m * v for m, v in zip(row, rgb)))) for row in MACHADO[kind]]
    return oklab(rgb)


def apart(a, b, kind=None):
    return 100 * sum((x - y) ** 2 for x, y in zip(seen(a, kind), seen(b, kind))) ** 0.5


def test_every_book_names_a_palette_that_exists():
    for f in (ROOT / "books").glob("*.json"):
        cfg = json.loads(f.read_text())
        assert cfg.get("palette") in knit.PALETTES, f.name
        assert knit.palette_for(cfg["slug"]) == cfg["palette"]
    assert knit.palette_for("a-book-with-no-settings") == knit.DEFAULT_PALETTE


def test_no_two_yarns_of_a_palette_can_be_mistaken_for_each_other():
    for key in knit.PALETTES:
        yarns = knit.yarns_of(key)
        assert [k for k, _, _ in yarns] == list("ABCDEU") and len({name for _, name, _ in yarns}) == 6
        for (_, n1, h1), (_, n2, h2) in combinations(yarns, 2):
            assert apart(h1, h2) >= 15, (key, n1, n2, "full colour vision")
            for kind in MACHADO:
                assert apart(h1, h2, kind) >= 8, (key, n1, n2, kind)


def test_the_first_palette_would_have_failed_this_check():
    # blue to red, as first drawn: its rose and its stone grey merge under red-green colour blindness
    assert min(apart("#c8745f", "#9c978c", kind) for kind in MACHADO) < 8


def test_cold_is_the_cool_colour_and_warm_the_warm_one():
    for key in knit.PALETTES:
        hexes = [hx for _, _, hx in knit.yarns_of(key)]
        cold, warm = seen(hexes[0]), seen(hexes[4])
        assert cold[2] < warm[2], key        # OKLab b: towards blue is below, towards yellow above
        assert max(abs(v) for v in seen(hexes[2])[1:]) < 0.02, key   # the middle yarn is a grey


def test_the_pattern_is_dyed_in_its_books_palette():
    for f in (ROOT / "site" / "data").glob("*/pattern.json"):
        K = json.loads(f.read_text())
        want = knit.yarns_of(knit.palette_for(K["book"]["slug"]))
        assert K["palette"]["key"] == knit.palette_for(K["book"]["slug"])
        assert [(y["key"], y["name"], y["hex"]) for y in K["yarns"]] == want
    shown = json.loads((ROOT / "site" / "data" / "palettes.json").read_text())["palettes"]
    assert {p["key"] for p in shown} == set(knit.PALETTES)
