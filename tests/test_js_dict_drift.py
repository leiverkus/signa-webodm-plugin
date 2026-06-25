"""Guard against drift between the dashboard JS dictionary list and the backend.

`signa/public/load_buttons.js` is a static <head> script (no Django rendering),
so it carries its own copy of the ArUco dictionary `(value, label)` pairs. That
list MUST match `signa_core.dictionaries.DICT_CHOICES` — the single source of
truth — or the dialog would offer dictionaries the worker can't build (or omit
ones it can). This test parses the JS array and asserts they are identical, so
any future edit to one side without the other fails CI.

Pure stdlib (regex) — no JS engine, no OpenCV, no WebODM.
"""
import os
import re

from signa_core.dictionaries import DICT_CHOICES

HERE = os.path.dirname(os.path.abspath(__file__))
JS_PATH = os.path.join(HERE, "..", "signa", "public", "load_buttons.js")

_PAIR = re.compile(r'\[\s*"(\d+)"\s*,\s*"([^"]*)"\s*\]')


def _js_dict_choices():
    """Extract the (value, label) pairs from the JS `var DICT_CHOICES = [...]`."""
    with open(JS_PATH, encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"var DICT_CHOICES\s*=\s*\[(.*?)\]\s*;", src, re.DOTALL)
    assert m, "could not locate `var DICT_CHOICES = [...]` in load_buttons.js"
    return [(v, label) for v, label in _PAIR.findall(m.group(1))]


def test_js_dict_choices_match_backend():
    js = _js_dict_choices()
    assert js == DICT_CHOICES, (
        "load_buttons.js DICT_CHOICES drifted from signa_core.dictionaries."
        "\n  JS:      %r\n  backend: %r" % (js, DICT_CHOICES)
    )
