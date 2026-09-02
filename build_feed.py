# -*- coding: utf-8 -*-
"""Books2Door Meta feed v2 - clean titles.

Source of truth: the existing DataFeedWatch Meta feed (read-only).
This script re-titles each item so g:title is the product name alone, and
relocates author / age / set into custom labels and binding into g:material.
"""
import argparse, csv, io, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
from parse_titles import parse_title

SOURCE_URL = "https://feeds.datafeedwatch.com/30774/918ec7a878786cddcf24f735d6cd42d80a7ff7fe.xml"
G = "http://base.google.com/ns/1.0"
ET.register_namespace("g", G)

# Where each extracted detail lands. Genre is dropped entirely. Binding is no
# longer a product_type crumb - it moved to g:material, collapsed to three values
# (2026-09-02), which leaves g:product_type identical to the DataFeedWatch value.
LABEL_AUTHOR, LABEL_AGE, LABEL_SET = "custom_label_0", "custom_label_1", "custom_label_4"
# custom_label_2 / custom_label_3 are Books2Door promo tags - preserved untouched.


def fetch(src):
    if re.match(r"^https?://", src):
        req = urllib.request.Request(src, headers={"User-Agent": "b2d-feed-v2/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read()
    with open(src, "rb") as fh:
        return fh.read()


def gtext(item, tag):
    el = item.find(f"{{{G}}}{tag}")
    return (el.text or "").strip() if el is not None and el.text else ""


def gset(item, tag, value):
    el = item.find(f"{{{G}}}{tag}")
    if el is None:
        el = ET.SubElement(item, f"{{{G}}}{tag}")
    el.text = value


def gclear(item, tag):
    """Drop a field entirely.

    DataFeedWatch began populating custom_label_0 (site category) and
    custom_label_4 (price bucket / SKU range) after this feed was built. Those
    are the slots we use for author and set, so a leftover source value would
    leave the label meaning two different things depending on the row. Each
    label has to carry exactly one meaning, so where we have no value the
    source's is removed rather than left in place.
    """
    for el in item.findall(f"{{{G}}}{tag}"):
        item.remove(el)


# Binding collapses to three materials. Anything that is not a book binding
# (Educational Toy, Yoga Cards) gets no material at all rather than a wrong one.
MATERIAL = {
    "paperback": "Paperback", "flexibound": "Paperback",
    "hardback": "Hardback", "hardcover": "Hardback",
    "sprayed edges hardback": "Hardback", "sprayed edge hardback": "Hardback",
    "leather bound hardback": "Hardback", "leather bound": "Hardback",
    "leather bound/hardback": "Hardback",
    "board book": "Board Book", "board books": "Board Book",
    "sprayed edges board book": "Board Book",
}


def build_material(fmt):
    """Map a binding to one of Paperback / Hardback / Board Book, or '' if it is
    not a book. A mixed binding takes the first one listed, so 'Paperback/Hardback'
    reads as Paperback and 'Board Book/Paperback' as Board Book."""
    f = (fmt or "").strip().lower()
    if not f:
        return ""
    if f in MATERIAL:
        return MATERIAL[f]
    first = re.split(r"\s*/\s*", f)[0].strip()
    return MATERIAL.get(first, "")


def build_product_type(original, genre, age, fmt, keep_format_crumb):
    """The original DataFeedWatch crumb, unchanged. Binding now lives in
    g:material, and genre and age have their own fields."""
    crumbs, seen = [], set()
    for c in [original]:
        c = (c or "").strip()
        if not c:
            continue
        key = re.sub(r"[^a-z0-9]", "", c.lower())
        # skip a crumb already implied by an earlier one (e.g. pt '9-14' vs age 'Ages 9-14')
        if key in seen or any(key in s or s in key for s in seen):
            continue
        seen.add(key)
        crumbs.append(c)
    return " > ".join(crumbs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=SOURCE_URL)
    ap.add_argument("--out-dir", default="docs")
    ap.add_argument("--basename", default="books2door_meta_feed_v2")
    ap.add_argument("--min-products", type=int, default=3500)
    ap.add_argument("--review-csv", default="")
    args = ap.parse_args()

    raw = fetch(args.source)
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        sys.exit("ERROR: no <channel> in source feed")
    items = channel.findall("item")
    if len(items) < args.min_products:
        sys.exit(f"ERROR: only {len(items)} items (min {args.min_products}) - refusing to publish")

    review, stats = [], {"author": 0, "format": 0, "age": 0, "genre": 0, "set": 0, "material": 0, "changed": 0}
    for item in items:
        orig_title = gtext(item, "title")
        p = parse_title(orig_title)

        new_title = p["name"]        # parse_title has already removed the pack phrase
        if not new_title:
            new_title = orig_title           # never ship an empty title

        gset(item, "title", new_title)
        for label, value, key in ((LABEL_AUTHOR, p["author"], "author"),
                                  (LABEL_AGE, p["age"], "age"),
                                  (LABEL_SET, p["pack"], "set")):
            if value:
                gset(item, label, value); stats[key] += 1
            else:
                gclear(item, label)
        material = build_material(p["format"])
        if material:
            gset(item, "material", material); stats["material"] += 1
        if p["format"]:
            stats["format"] += 1
        if p["genre"]:
            stats["genre"] += 1

        pt = build_product_type(gtext(item, "product_type"), p["genre"], p["age"],
                                p["format"], False)
        if pt:
            gset(item, "product_type", pt)
        if new_title != orig_title:
            stats["changed"] += 1

        review.append({"id": gtext(item, "id"), "old_title": orig_title, "new_title": new_title,
                       "author": p["author"], "format": p["format"], "age": p["age"],
                       "genre": p["genre"], "material": material, "set": p["pack"],
                       "pack_count": p["pack_count"], "product_type": pt})

    os.makedirs(args.out_dir, exist_ok=True)
    xml_path = os.path.join(args.out_dir, args.basename + ".xml")
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)

    csv_cols = ["id", "title", "description", "link", "image_link", "additional_image_link",
                "price", "sale_price", "availability", "brand", "gtin", "item_group_id",
                "condition", "material", "product_type", "google_product_category",
                "custom_label_0", "custom_label_1", "custom_label_2", "custom_label_3",
                "custom_label_4"]
    csv_path = os.path.join(args.out_dir, args.basename + ".csv")
    with io.open(csv_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=csv_cols)
        w.writeheader()
        for item in items:
            w.writerow({c: gtext(item, c) for c in csv_cols})

    if args.review_csv:
        with io.open(args.review_csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(review[0].keys()))
            w.writeheader(); w.writerows(review)

    n = len(items)
    print(f"items            : {n}")
    print(f"titles rewritten : {stats['changed']} ({stats['changed']*100//n}%)")
    for k in ("author", "age", "set", "material", "format", "genre"):
        print(f"{k:17s}: {stats[k]} ({stats[k]*100//n}%)")
    print(f"wrote {xml_path}")
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
