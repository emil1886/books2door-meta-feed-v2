# -*- coding: utf-8 -*-
"""Split a Books2Door feed title into: clean product name + author / format / age / genre / set."""
import re

FORMAT_WORDS = [
    "Sprayed Edges Hardback", "Sprayed Edge Hardback", "Sprayed Edges Board Book",
    "Sprayed Edges Paperback", "Leather Bound/Hardback", "Leather Bound Hardback",
    "Leather Bound", "Paperback/Hardback", "Hardback/Paperback", "Board Book/Paperback",
    "Paperback/Board Book", "Hardback/Board Book", "Educational Toys", "Educational Toy",
    "Board Books", "Board Book", "Board book", "Flexibound", "Hardcover", "Hardback",
    "Paperback", "Yoga Cards", "Cards", "Jigsaw", "Audiobook",
]
FORMAT_CANON = {
    "board book": "Board Book", "board books": "Board Book", "hardcover": "Hardback",
    "educational toys": "Educational Toy", "hardback/paperback": "Paperback/Hardback",
    "leather bound/hardback": "Leather Bound Hardback", "sprayed edge hardback": "Sprayed Edges Hardback",
    "paperback/board book": "Board Book/Paperback",
}
GENRES = {
    "fiction": "Fiction", "non fiction": "Non-Fiction", "non-fiction": "Non-Fiction",
    "nonfiction": "Non-Fiction", "young adult": "Young Adult", "manga": "Manga",
    "graphic novel": "Graphic Novels", "graphic novels": "Graphic Novels", "poetry": "Poetry",
}
AGE_RE = re.compile(
    r"^ages?\s*\d{1,2}\s*(?:years?|months?|yrs?)?\s*(?:[-\u2013\u2014to]+\s*\d{1,2}\s*(?:years?|months?)?)?\s*\+?$",
    re.I)
# "(Book 1-4)", "(Books 1-4)", "(Volume 2)"
BOOKNUM_RE = re.compile(r"\(\s*(?:books?|vol(?:ume)?s?)\.?\s*[\d\s\u2013\-,&+]+\)", re.I)
# "5 Books Collection Set", "3 Books Box Set", "10 Picture Books", "2 Books Set", "Box Set"
SET_RE = re.compile(
    r"(?:\b\d{1,3}\s+)?(?:picture\s+|illustrated\s+|story\s+)?\bbooks?\s+"
    r"(?:collection\s+)?(?:box\s+)?(?:set|collection)\b"
    r"|\bbox\s+set\b|\bcollection\s+set\b|\b\d{1,3}\s+picture\s+books\b", re.I)
_MOD = r"(?:illustrated\s+|picture\s+|story\s+|storybook\s+)?"
_SETWORD = r"(?:(?:collection\s+)?(?:box\s+)?(?:set|collection))"
# With a set word ('4 Books Collection Set') the phrase is unambiguous wherever it
# sits. A bare count ('5 Books') is only a pack when the end or punctuation follows
# - that keeps 'CoComelon 24 Book Countdown' and '4 Books & Backpack Bundle' intact.
PACK_SET_RE = re.compile(
    r"\b" + _MOD + r"(\d{1,3})\s+" + _MOD + r"books?\s+" + _SETWORD + r"\b", re.I)
PACK_BARE_RE = re.compile(
    r"\b" + _MOD + r"(\d{1,3})\s+" + _MOD + r"books?\b"
    r"(?=\s*(?:$|[,:;(]|[-\u2013]\s))", re.I)


def _pack_match(text):
    return PACK_SET_RE.search(text or "") or PACK_BARE_RE.search(text or "")


def parse_pack(title):
    """-> (count:int|0, label:str). Label is the full descriptor where one is
    stated ('4 Books Collection Set'), else the bare count ('5 Books')."""
    t = re.sub(r"\s+", " ", (title or "")).strip()
    m = _pack_match(t)
    if not m:
        return 0, ""
    count = int(m.group(1))
    if count < 2 or count > 60:          # 1-book and absurd counts are not packs
        return 0, ""
    desc = re.sub(r"\s+", " ", m.group(0)).strip(" ,:;-\u2013")
    desc = " ".join(w if w[:1].isupper() else w.capitalize() for w in desc.split())
    return count, desc


def strip_pack(title):
    """Remove the pack phrase from a title, tidying the punctuation it leaves."""
    m = _pack_match(title or "")
    if not m:
        return (title or "").strip()
    out = (title[:m.start()] + " " + title[m.end():])
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,:;])", r"\1", out)
    out = re.sub(r"\(\s*\)", "", out)
    return out.strip(" ,:;-\u2013")


def _canon_format(s):
    return FORMAT_CANON.get(s.strip().lower(), s.strip())

def _norm_age(s):
    s = re.sub(r"\s*([-\u2013\u2014])\s*", "-", s.strip())
    s = re.sub(r"^age\b", "Ages", s, flags=re.I)
    s = re.sub(r"^ages\b", "Ages", s, flags=re.I)
    return re.sub(r"\s+", " ", s)

def _classify(seg):
    """Return ('format'|'age'|'genre'|None, canonical_value) for a trailing segment."""
    s = seg.strip().strip("-\u2013 ").strip()
    if not s:
        return None, None
    low = s.lower()
    if low in GENRES:
        return "genre", GENRES[low]
    if AGE_RE.match(s):
        return "age", _norm_age(s)
    for f in FORMAT_WORDS:
        if low == f.lower():
            return "format", _canon_format(s)
    return None, None

def _peel_inline(seg):
    """Peel known trailing tokens glued on with a bare '-' e.g. 'Non Fiction- Hardback'."""
    out = []
    changed = True
    while changed:
        changed = False
        for f in FORMAT_WORDS:
            m = re.search(r"[-\u2013]\s*" + re.escape(f) + r"\s*$", seg, re.I)
            if m:
                out.append(("format", _canon_format(m.group(0).lstrip("-\u2013 "))))
                seg = seg[:m.start()].strip()
                changed = True
                break
    return seg, out

def parse_title(title):
    t = re.sub(r"\s+", " ", (title or "").replace("\u2013", "-").replace("\u2014", "-")).strip()
    fmt = age = genre = ""
    parts = [p.strip() for p in t.split(" - ")]

    # peel classifiable segments off the end
    while len(parts) > 1:
        kind, val = _classify(parts[-1])
        if kind is None:
            break
        if kind == "format" and not fmt:
            fmt = val
        elif kind == "age" and not age:
            age = val
        elif kind == "genre" and not genre:
            genre = val
        parts.pop()

    head = " - ".join(parts).strip()
    head, extra = _peel_inline(head)
    for kind, val in extra:
        if kind == "format" and not fmt:
            fmt = val
    # a bare-dash age/genre still glued to head
    m = re.search(r"[-\u2013]\s*([^-]{2,20})$", head)
    if m:
        kind, val = _classify(m.group(1))
        if kind == "age" and not age:
            age, head = val, head[:m.start()].strip()
        elif kind == "genre" and not genre:
            genre, head = val, head[:m.start()].strip()

    # ---- author ----
    author = ""
    am = re.search(r"\bby\s+(.+)$", head, re.I)
    if am:
        tail = am.group(1)
        cut = len(tail)
        cm = re.search(r"[:(]", tail)
        if cm:
            cut = min(cut, cm.start())
        sm = SET_RE.search(tail)
        if sm:
            cut = min(cut, sm.start())
        cand = tail[:cut].strip(" ,:-")
        # authors are short and word-like, not sentences
        if cand and len(cand) <= 60 and cand.count(" ") <= 7:
            author = cand

    # ---- set / pack descriptor ----
    setinfo = ""
    bn = BOOKNUM_RE.search(head)
    sm = SET_RE.search(head)
    bits = []
    if bn:
        bits.append(re.sub(r"\s+", " ", bn.group(0)).strip())
    if sm:
        bits.append(re.sub(r"\s+", " ", sm.group(0)).strip())
    setinfo = " ".join(bits)

    # ---- clean name: strip the author phrase only ----
    name = head
    if author:
        name = re.sub(r"\s*\bby\s+" + re.escape(author) + r"\b", "", name, count=1, flags=re.I)
    name = re.sub(r"\s*:\s*$", "", name)
    name = re.sub(r"\s{2,}", " ", name).strip(" ,:-\u2013")
    name = re.sub(r"\(\s*\)", "", name).strip(" ,:-")
    if not name:
        name = head

    # fallback: format stated mid-title or in parens, e.g. 'Hardcover (Leather-bound)'
    if not fmt:
        for f in sorted(FORMAT_WORDS, key=len, reverse=True):
            if re.search(r"\b" + re.escape(f) + r"\b", t, re.I):
                fmt = _canon_format(f)
                break
    if not age:
        am2 = re.search(r"\bages?\s*\d{1,2}\s*(?:[-\u2013to]+\s*\d{1,2})?\s*\+?", t, re.I)
        if am2:
            age = _norm_age(am2.group(0))

    pack_count, pack = parse_pack(name)

    return {"name": name, "author": author, "format": fmt, "age": age,
            "genre": genre, "set": setinfo, "pack": pack, "pack_count": pack_count}
