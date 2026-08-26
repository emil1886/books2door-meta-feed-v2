# -*- coding: utf-8 -*-
"""Books2Door Meta feed v2 - clean titles.

Source of truth: the existing DataFeedWatch Meta feed (read-only).
This script re-titles each item so g:title is the product name alone, and
relocates author / format / age / genre into custom labels + product_type.
"""
import argparse, csv, io, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
from parse_titles import parse_title, strip_pack

SOURCE_URL = "https://feeds.datafeedwatch.com/30774/918ec7a878786cddcf24f735d6cd42d80a7ff7fe.xml"
G = "http://base.google.com/ns/1.0"
ET.register_namespace("g", G)

# Where each extracted detail lands. Genre and format get no label: Emil ruled
# both unimportant for this feed (2026-08-26). Format survives only as a
# trailing product_type crumb, because 30 items are otherwise indistinguishable.
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


def build_product_type(original, genre, age, fmt, keep_format_crumb):
    """Original DFW crumb, then format purely to disambiguate same-title editions.
    Genre is deliberately dropped; age now has its own label."""
    crumbs, seen = [], set()
    for c in [original, (fmt if keep_format_crumb else "")]:
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
    ap.add_argument("--keep-set-in-title", action="store_true", default=False,
                    help="keep '3 Books Collection Set' in the title; off by default "
                         "because it now has its own label (custom_label_4)")
    ap.add_argument("--format-in-product-type", action="store_true", default=True)
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

    review, stats = [], {"author": 0, "format": 0, "age": 0, "genre": 0, "set": 0, "changed": 0}
    for item in items:
        orig_title = gtext(item, "title")
        p = parse_title(orig_title)

        new_title = p["name"]
        if not args.keep_set_in_title and p["pack"]:
            stripped = strip_pack(new_title)
            if len(stripped) >= 8:
                new_title = stripped
        if not new_title:
            new_title = orig_title           # never ship an empty title

        gset(item, "title", new_title)
        if p["author"]:
            gset(item, LABEL_AUTHOR, p["author"]); stats["author"] += 1
        if p["age"]:
            gset(item, LABEL_AGE, p["age"]); stats["age"] += 1
        if p["pack"]:
            gset(item, LABEL_SET, p["pack"]); stats["set"] += 1
        if p["format"]:
            stats["format"] += 1
        if p["genre"]:
            stats["genre"] += 1

        pt = build_product_type(gtext(item, "product_type"), p["genre"], p["age"],
                                p["format"], args.format_in_product_type)
        if pt:
            gset(item, "product_type", pt)
        if new_title != orig_title:
            stats["changed"] += 1

        review.append({"id": gtext(item, "id"), "old_title": orig_title, "new_title": new_title,
                       "author": p["author"], "format": p["format"], "age": p["age"],
                       "genre": p["genre"], "set": p["pack"],
                       "pack_count": p["pack_count"], "product_type": pt})

    os.makedirs(args.out_dir, exist_ok=True)
    xml_path = os.path.join(args.out_dir, args.basename + ".xml")
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)

    csv_cols = ["id", "title", "description", "link", "image_link", "additional_image_link",
                "price", "sale_price", "availability", "brand", "gtin", "item_group_id",
                "condition", "product_type", "google_product_category",
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
    for k in ("author", "age", "set", "format", "genre"):
        print(f"{k:17s}: {stats[k]} ({stats[k]*100//n}%)")
    print(f"wrote {xml_path}")
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
