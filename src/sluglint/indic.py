"""Comparing names written in an Indic script.

Tier 2 decides whether two character cues or two locations are the same thing
by string similarity. That works on Latin text and quietly fails on Telugu,
Devanagari, Tamil and their neighbours, for two reasons.

**An abugida does not compare like an alphabet.** One visual letter is a base
consonant plus a vowel sign plus possibly a virama and another consonant, so a
one-vowel typo moves several code points at once. RAJU written with a short
final vowel and RAJU written with a long one, which is exactly the drift this
engine exists to catch, score 0.75 against each other: under the 0.80
threshold, so it is missed. Folded to a comparison key they score 1.00 and get
reported.

**A code-mixed draft cues one person both ways.** A writer sets a cue in Telugu
on page 4 and in Latin on page 40. That is one actor and one contract, and no
amount of code-point comparison will ever see it, because the two strings share
no characters at all. Transliterating both to one romanisation does see it:
the Telugu spelling of KRISHNA folds to 'krishna' and matches the Latin cue
exactly.

The fold is deliberately lossy. It is not a romanisation anyone would publish,
it is a comparison key. Aspirates collapse, retroflex and dental collapse,
vowel length collapses. Two spellings a reader would call the same name have to
land on the same key, and that is the only property it needs to have.

`indic-transliteration` is optional (`pip install "sluglint[indic]"`). Without
it every function here reports "nothing to fold" and tier 2 behaves exactly as
it did before.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

# Devanagari through Malayalam. Written as escapes so the source stays ASCII;
# this one range covers Hindi, Marathi, Bengali, Gurmukhi, Gujarati, Odia,
# Tamil, Telugu, Kannada and Malayalam.
INDIC_RANGE = re.compile(r"[\u0900-\u0d7f]")

# Which block a string sits in decides which transliteration table to use.
# The first block with a character present wins.
_BLOCKS = [
    ("devanagari", "\u0900", "\u097f"),
    ("bengali", "\u0980", "\u09ff"),
    ("gurmukhi", "\u0a00", "\u0a7f"),
    ("gujarati", "\u0a80", "\u0aff"),
    ("oriya", "\u0b00", "\u0b7f"),
    ("tamil", "\u0b80", "\u0bff"),
    ("telugu", "\u0c00", "\u0c7f"),
    ("kannada", "\u0c80", "\u0cff"),
    ("malayalam", "\u0d00", "\u0d7f"),
]

# ISO 15919 comes out carrying distinctions a cue comparison does not want. A
# writer who types the retroflex on one page and the dental on the next has
# made one name, not two, so both sides fold to the same letter. Applied only
# to transliterated text: 'c' is the ISO letter for the sound a Latin cue
# spells 'ch', and rewriting it inside Latin input would turn CHITRA into
# 'chhitra'.
_ISO_FOLD = {
    "r\u0325": "ri", "l\u0325": "li",     # vocalic r and l
    "\u1e63": "sh", "\u015b": "sh",       # retroflex and palatal sibilants
    "\u1e6d": "t", "\u1e0d": "d",         # retroflex stops
    "\u1e47": "n", "\u1e45": "n", "\u00f1": "n",
    "\u1e41": "m", "\u1e25": "h",
    "c": "ch",
}
# Hindi, Marathi and their neighbours delete the inherent final vowel that ISO
# writes out, so a cue romanised from Devanagari ends in an 'a' that the Latin
# cue for the same name never had.
_SCHWA_DELETING = {"devanagari", "gujarati", "bengali", "oriya", "gurmukhi"}


def _sanscript():
    """The optional dependency, or (None, None). Imported once, on demand."""
    try:
        from indic_transliteration import sanscript  # noqa: PLC0415
        from indic_transliteration.sanscript import transliterate  # noqa: PLC0415
    except ImportError:
        return None, None
    return sanscript, transliterate


def script_of(text: str) -> str | None:
    """Which Indic block this string is written in, or None for Latin."""
    for name, lo, hi in _BLOCKS:
        if any(lo <= ch <= hi for ch in text):
            return name
    return None


def is_indic(text: str) -> bool:
    return bool(INDIC_RANGE.search(text))


@lru_cache(maxsize=4096)
def fold(text: str) -> str:
    """A comparison key: lowercase ASCII, one spelling per sound.

    Latin input folds the same way so that a native-script cue and a Latin cue
    meet on common ground. Returns '' when there is nothing left to compare, or
    when the optional dependency is missing.
    """
    block = script_of(text)
    if block:
        sanscript, transliterate = _sanscript()
        scheme = getattr(sanscript, block.upper(), None) if sanscript else None
        if scheme is None:
            return ""  # dependency absent: the caller falls back to raw comparison
        text = transliterate(text, scheme, sanscript.ISO).lower()
        for src, dst in _ISO_FOLD.items():
            text = text.replace(src, dst)
        if block in _SCHWA_DELETING:
            text = re.sub(r"a\b", "", text)
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text)


def comparable(a: str, b: str) -> tuple[str, str] | None:
    """Fold a pair for comparison, or None when the raw strings will do.

    Returns None unless at least one side is in an Indic script, so an
    all-Latin draft goes down exactly the path it always did.
    """
    if not (is_indic(a) or is_indic(b)):
        return None
    fa, fb = fold(a), fold(b)
    return (fa, fb) if fa and fb else None
