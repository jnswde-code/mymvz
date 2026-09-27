"""Word-level differences between two versions of a text, for the history (#37)."""

import re
from difflib import SequenceMatcher

# Words and the whitespace between them, so line breaks survive the diff.
_TOKENS = re.compile(r"\s+|[^\s]+")


def word_diff(old: str, new: str) -> list[tuple[str, str]]:
    """Segments `(kind, text)` with kind `same`, `removed` or `added`."""
    a, b = _TOKENS.findall(old), _TOKENS.findall(new)
    segments = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            segments.append(("same", "".join(a[i1:i2])))
            continue
        if i1 < i2:
            segments.append(("removed", "".join(a[i1:i2])))
        if j1 < j2:
            segments.append(("added", "".join(b[j1:j2])))
    return segments
