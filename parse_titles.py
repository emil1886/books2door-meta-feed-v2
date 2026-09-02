# -*- coding: utf-8 -*-
"""Split a Books2Door feed title into a clean product name plus its details.

The source titles crammed everything into one string, in no reliable order and
with inconsistent separators ('Ages 0-5- Paperback', 'Backpack- Ages 1-7',
'Paperback (With A Free Audiobook)'). Peeling segments off the end therefore
stalls at the first thing it cannot classify. Instead this finds each detail
wherever it sits, excises it, and heals the punctuation left behind.
"""
import re

FORMAT_WORDS = [
    "Sprayed Edges Hardback", "Sprayed Edge Hardback", "Sprayed Edges Board Book",
    "Sprayed Edges Paperback", "Leather Bound/Hardback", "Leather Bound Hardback",
    "Leather Bound", "Paperback/Hardback", "Hardback/Paperback", "Board Book/Paperback",
    "Paperback/Board Book", "Hardback/Board Book", "Educational Toys", "Educational Toy",
    "Board Books", "Board Book", "Flexibound", "Hardcover", "Hardback", "Paperback",
    "Yoga Cards",
    "Hardabck", "Hardaback",          # misspelt in the source on 2 products
]
FORMAT_CANON = {
    "board books": "Board Book", "hardcover": "Hardback",
    "educational toys": "Educational Toy", "hardback/paperback": "Paperback/Hardback",
    "leather bound/hardback": "Leather Bound Hardback",
    "sprayed edge hardback": "Sprayed Edges Hardback",
    "hardabck": "Hardback", "hardaback": "Hardback",
    "paperback/board book": "Board Book/Paperback",
}
GENRES = {
    "fiction": "Fiction", "non fiction": "Non-Fiction", "non-fiction": "Non-Fiction",
    "nonfiction": "Non-Fiction", "young adult": "Young Adult", "manga": "Manga",
    "graphic novel": "Graphic Novels", "graphic novels": "Graphic Novels",
    "poetry": "Poetry",
}

# 'Ages 0-5', 'Age 3+', 'Ages 3 Years+', 'Ages 18 Months+', 'Ages 14 years and up'.
AGE_FIND = re.compile(
    r"\bages?\s*\d{1,2}\s*(?:years?|months?|yrs?)?\s*"
    r"(?:(?:[-\u2013\u2014]|to)\s*\d{1,2}\s*(?:years?|months?)?"
    r"|years?\s+and\s+up|and\s+up|\+)?\s*\+?", re.I)
_ONE_GENRE = r"(?:non[\s-]?fiction|fiction|young adult|manga|graphic novels?|poetry)"
# matches combinations too: 'Fiction/Non Fiction', 'Non-Fiction & Fiction'
GENRE_FIND = re.compile(
    _ONE_GENRE + r"(?:\s*[/&+]\s*" + _ONE_GENRE + r")*", re.I)
_ONE_FORMAT = r"(?:" + "|".join(re.escape(f) for f in
                                sorted(FORMAT_WORDS, key=len, reverse=True)) + r")"
# formats are often stated as a pair: 'Paperback/Flexibound', 'Paperback-Hardback',
# 'Paperback/Deckled Edge Paperback'. Match the whole run, not just one member.
FORMAT_FIND = re.compile(
    r"\b" + _ONE_FORMAT + r"(?:\s*[/-]\s*(?:[\w'’]+\s+){0,2}" + _ONE_FORMAT + r")*\b", re.I)
# a bracketed aside that is really just the format, e.g. '(A Big Board Book)'
FORMAT_PAREN = re.compile(r"\s*\([^)]*\b" + _ONE_FORMAT + r"\b[^)]*\)", re.I)

_MOD = r"(?:illustrated\s+|picture\s+|story\s+|storybook\s+|activity\s+|board\s+)?"
_SETWORD = r"(?:(?:collection\s+)?(?:box\s+)?(?:set|collection))"
# With a set word ('4 Books Collection Set') the phrase is unambiguous wherever it
# sits. A bare count ('5 Books') only counts before the end, punctuation or '&' -
# so 'CoComelon Advent Calendar: 24 Book Countdown' keeps its name, while
# 'Lift-The-Flap 5 Books & Red Backpack' still yields '5 Books'.
PACK_SET_RE = re.compile(
    r"\b" + _MOD + r"(\d{1,3})\s+" + _MOD + r"books?\s+(?:[\w'’]+\s+){0,2}" + _SETWORD + r"\b",
    re.I)
PACK_BARE_RE = re.compile(
    r"\b" + _MOD + r"(\d{1,3})\s+" + _MOD + r"books?\b"
    r"(?=\s*(?:$|[,:;(&]|by\b|[-\u2013]\s))", re.I)

BOOKNUM_RE = re.compile(r"\(\s*(?:books?|vol(?:ume)?s?)\.?\s*[\d\s\u2013\-,&+]+\)", re.I)
_SEP_BEFORE = re.compile(r"[-\u2013\u2014:,(/]\s*$")
_AUTHOR_STOPS = (r"\b\d{1,3}\s+" + _MOD + r"books?\b", r"\bcomplete\s+collection\b",
                 r"\bcollection\b", r"\bbox\s+set\b", r"\billustrated\b")


def _canon_format(s):
    s = s.strip()
    if s.lower() in FORMAT_CANON:
        return FORMAT_CANON[s.lower()]
    first = re.split(r"\s*[/-]\s*", s)[0].strip()   # 'Paperback/Hardback' -> 'Paperback'
    return FORMAT_CANON.get(first.lower(), first)


def _canon_genre(s):
    parts = [p.strip() for p in re.split(r"[/&+]", s) if p.strip()]
    out = []
    for p in parts:
        v = GENRES.get(re.sub(r"[\s-]+", " ", p.lower()), p)
        if v not in out:
            out.append(v)
    return "/".join(out)


def _norm_age(s):
    s = re.sub(r"\s*([-\u2013\u2014])\s*", "-", s.strip())
    s = re.sub(r"^ages?\b", "Ages", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def _heal(text):
    """Tidy the punctuation left behind after cutting a span out."""
    out = re.sub(r"\s{2,}", " ", text)
    out = re.sub(r"(?:\s*[-\u2013\u2014:,]\s*){2,}", " - ", out)
    out = re.sub(r"\s+([,:;])", r"\1", out)
    out = re.sub(r"\(\s*\)", "", out)
    return out.strip(" ,:;/-\u2013\u2014")


def _metadata_position(text, start, end):
    """Metadata sits after a separator, or at the very end of the title."""
    return end >= len(text.rstrip()) or bool(_SEP_BEFORE.search(text[:start]))


def _take(text, rx, canon):
    """Excise the last metadata-positioned match of rx. -> (text, value)."""
    chosen = None
    for m in rx.finditer(text):
        if _metadata_position(text, m.start(), m.end()):
            chosen = m
    if chosen is None:
        return text, ""
    return _heal(text[:chosen.start()] + text[chosen.end():]), canon(chosen.group(0))


def _take_all(text, rx, canon):
    """Excise EVERY match of rx, wherever it sits. -> (text, value of the last one).

    Used for age and format: Emil's rule is that any title mentioning 'Ages',
    'Paperback' or 'Hardback' must be renamed, so position is irrelevant here.
    """
    matches = list(rx.finditer(text))
    if not matches:
        return text, ""
    out, last = [], 0
    for m in matches:
        out.append(text[last:m.start()])
        last = m.end()
    out.append(text[last:])
    return _heal("".join(out)), canon(matches[-1].group(0))


def _pack_match(text):
    return PACK_SET_RE.search(text or "") or PACK_BARE_RE.search(text or "")


def parse_pack(title):
    """-> (count:int|0, label:str), e.g. (4, '4 Books Collection Set'), (5, '5 Books')."""
    t = re.sub(r"\s+", " ", (title or "")).strip()
    m = _pack_match(t)
    if not m:
        return 0, ""
    count = int(m.group(1))
    if count < 2 or count > 60:          # 1-book and absurd counts are not packs
        return 0, ""
    desc = re.sub(r"\s+", " ", m.group(0)).strip(" ,:;-\u2013")
    # 'Board' is a binding, not a pack size: '18 Board Books Set' -> '18 Books Set'
    desc = re.sub(r"\bboard\s+(?=books?\b)", "", desc, flags=re.I)
    return count, " ".join(w if w[:1].isupper() else w.capitalize() for w in desc.split())


def strip_pack(title):
    m = _pack_match(title or "")
    if not m:
        return (title or "").strip()
    return _heal(title[:m.start()] + " " + title[m.end():])


def parse_title(title):
    t = re.sub(r"\s+", " ", (title or "")).strip()

    # Pack first, while the phrase is still intact: removing formats later would
    # eat 'Board Books' out of '18 Board Books Set' and leave '18 Set' behind.
    pack_count, pack = parse_pack(t)
    name = strip_pack(t) if pack else t

    # A bracket whose contents are really just the format goes whole, so that
    # '(A Big Board Book)' does not decay into '(A Big)'.
    fmt = ""
    pm = FORMAT_PAREN.search(name)
    if pm:
        inner = FORMAT_FIND.search(pm.group(0))
        fmt = _canon_format(inner.group(0)) if inner else ""
        name = _heal(name[:pm.start()] + " " + name[pm.end():])

    # Format next: it is the most reliably worded, and removing it exposes an
    # age that was jammed against it ('Ages 0-5- Paperback').
    name, fmt2 = _take_all(name, FORMAT_FIND, _canon_format)
    fmt = fmt or fmt2
    # a marketing note the format left dangling, e.g. '(Includes Free Audiobook)'
    name = re.sub(r"[-\u2013:]?\s*\((?:includes?|with|free|a fold-out)[^)]*\)\s*$",
                  "", name, flags=re.I).strip(" ,:;-\u2013")
    name, age = _take_all(name, AGE_FIND, _norm_age)
    name, genre = _take(name, GENRE_FIND, _canon_genre)

    author = ""
    # require something before 'by', so a title that opens with it keeps its name
    # ('By Ash, Oak and Thorn Series By Melissa Harrison' -> author is Melissa Harrison)
    # ...and take the LAST 'by', so 'Fifty Shades as Told by Christian Trilogy by
    # E L James' credits E L James rather than the whole phrase after the first one.
    seps = list(re.finditer(r"(?<=\S)\s+by\s+", name, re.I))
    if seps:
        am = seps[-1]
        tail = name[am.end():]
        cut = len(tail)
        cm = re.search(r"[:(]", tail)
        if cm:
            cut = min(cut, cm.start())
        for pat in _AUTHOR_STOPS:
            em = re.search(pat, tail, re.I)
            if em:
                cut = min(cut, em.start())
        cand = tail[:cut].strip(" ,:-")
        if cand and len(cand) <= 60 and cand.count(" ") <= 7:
            author = cand
            name = _heal(name[:am.start()] + " " + tail[cut:])

    bn = BOOKNUM_RE.search(t)
    setinfo = " ".join(filter(None, [bn.group(0).strip() if bn else "", pack]))

    if not name:
        name = t
    return {"name": name, "author": author, "format": fmt, "age": age,
            "genre": genre, "set": setinfo, "pack": pack, "pack_count": pack_count}
