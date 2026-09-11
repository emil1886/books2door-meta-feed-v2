# -*- coding: utf-8 -*-
"""Books2Door Meta feed v2 - clean titles.

Source of truth: the existing DataFeedWatch Meta feed (read-only).
This script re-titles each item so g:title is the product name alone, and
puts author and age into custom labels, binding into g:material, pack
quantity into g:size, and the website categories into g:product_type.

Category membership comes live from DataFeedWatch, which supplies a second
<g:product_type> listing every Shopify collection a product belongs to.
"""
import argparse, csv, io, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
from parse_titles import parse_title

SOURCE_URL = "https://feeds.datafeedwatch.com/30774/918ec7a878786cddcf24f735d6cd42d80a7ff7fe.xml"
G = "http://base.google.com/ns/1.0"
ET.register_namespace("g", G)

# Where each extracted detail lands. Genre is dropped entirely. Binding is no
# longer a product_type crumb - it moved to g:material, collapsed to three values
# (2026-09-02), which leaves g:product_type identical to the DataFeedWatch value.
LABEL_AUTHOR, LABEL_AGE = "custom_label_0", "custom_label_1"
# Pack quantity moved to g:size on 2026-09-02, which frees custom_label_4.
# custom_label_2 / custom_label_3 are Books2Door promo tags, and custom_label_4
# is now DataFeedWatch's own again - all three pass through untouched.


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

    DataFeedWatch began populating custom_label_0 with the site category after
    this feed was built, and that is the slot we use for the author. A leftover
    source value would leave the label meaning two different things depending on
    the row, so where we have no value of our own the source's is removed rather
    than left in place. The same applies to g:size, which we own outright.
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


def load_nav_categories(path):
    """-> (collection title -> nav label, set of nav parents to drop).

    DataFeedWatch supplies collection membership live, in a second
    <g:product_type> holding a ';'-separated list of collection TITLES. This
    file only translates those titles into the labels the shopper actually sees
    in the nav ("Bestselling Books - Top 200" -> "Books2Door Top 100") and names
    the nav parents worth dropping. Membership itself is never cached here, so
    new products are categorised the day they appear.
    """
    if not path or not os.path.exists(path):
        return {}, set()
    with io.open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return d.get("nav_label_by_collection_title", {}), set(d.get("parents", []))


def source_collections(item):
    """Every Shopify collection DataFeedWatch says this product belongs to.

    DataFeedWatch has changed how it sends these twice, so read both shapes:

    * <internal_label> repeated, one collection each - the current shape. Note
      it is NOT in the g: namespace, like rrp and perc_off.
    * a second <g:product_type> holding a ';'-separated list - the older shape,
      which capped at 750 characters and truncated 81 products mid-word.

    Falling back keeps the feed working across another upstream change rather
    than silently emptying the category field, which is what happened on
    2026-09-10 when the second product_type disappeared.
    """
    labels = [(e.text or "").strip() for e in item.findall("internal_label")]
    if labels:
        return [x for x in labels if x]
    tags = item.findall(f"{{{G}}}product_type")
    if len(tags) > 1:
        return [x.strip() for x in (tags[1].text or "").split(";") if x.strip()]
    return []


def categories_from_source(item, label_by_title, parents):
    """The site categories for one product.

    Only collections that appear in the site nav are kept - the rest are
    inventory bookkeeping (B2D Listed Books, Core Products) or price bands,
    which would swamp the real categories at a median of 10 per product.
    """
    out = []
    for title in source_collections(item):
        label = label_by_title.get(title)
        if label and label not in parents and label not in out:
            out.append(label)
    return sorted(out)


def build_product_type(original, categories):
    """DataFeedWatch's own crumb first, so product sets filtering on it keep
    matching, then the website categories as they are labelled in the site's nav
    dropdowns. Meta matches any level of the path with 'contains'."""
    crumbs, seen = [], set()
    for c in [original] + list(categories):
        c = (c or "").strip()
        if not c:
            continue
        # 'Ages 7-9' and DataFeedWatch's '7-9' are the same crumb, so normalise
        # the prefix away before comparing; distinct categories stay distinct.
        key = re.sub(r"[^a-z0-9]", "", re.sub(r"^ages?\s+", "", c.lower()))
        if key in seen:
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
    ap.add_argument("--nav-categories", default=os.path.join("data", "nav_categories.json"),
                    help="collection title -> nav label map, and the parents to drop")
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

    label_by_title, parents = load_nav_categories(args.nav_categories)
    print(f"nav category map: {len(label_by_title)} collections, {len(parents)} parents dropped"
          if label_by_title else
          "nav category map: NONE - product_type keeps only the source crumb")

    review, stats = [], {"author": 0, "format": 0, "age": 0, "genre": 0, "set": 0,
                         "material": 0, "categorised": 0, "changed": 0}
    for item in items:
        orig_title = gtext(item, "title")
        p = parse_title(orig_title)

        new_title = p["name"]        # parse_title has already removed the pack phrase
        if not new_title:
            new_title = orig_title           # never ship an empty title

        gset(item, "title", new_title)
        for label, value, key in ((LABEL_AUTHOR, p["author"], "author"),
                                  (LABEL_AGE, p["age"], "age")):
            if value:
                gset(item, label, value); stats[key] += 1
            else:
                gclear(item, label)

        # How many books are in the pack. Every pack phrase we recognise states
        # 'book(s)', so the unit is always accurate.
        if p["pack_count"]:
            gset(item, "size", f'{p["pack_count"]} Books'); stats["set"] += 1
        else:
            gclear(item, "size")
        material = build_material(p["format"])
        if material:
            gset(item, "material", material); stats["material"] += 1
        if p["format"]:
            stats["format"] += 1
        if p["genre"]:
            stats["genre"] += 1

        product_cats = categories_from_source(item, label_by_title, parents)
        if product_cats:
            stats["categorised"] += 1
        pt = build_product_type(gtext(item, "product_type"), product_cats)
        # Collapse DataFeedWatch's two product_type tags into the single one Meta
        # reads - leaving both would make the field ambiguous.
        gclear(item, "product_type")
        if pt:
            gset(item, "product_type", pt)
        if new_title != orig_title:
            stats["changed"] += 1

        review.append({"id": gtext(item, "id"), "old_title": orig_title, "new_title": new_title,
                       "author": p["author"], "format": p["format"], "age": p["age"],
                       "genre": p["genre"], "material": material, "set": p["pack"],
                       "pack_count": p["pack_count"], "n_categories": len(product_cats),
                       "product_type": pt})

    os.makedirs(args.out_dir, exist_ok=True)
    xml_path = os.path.join(args.out_dir, args.basename + ".xml")
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)

    csv_cols = ["id", "title", "description", "link", "image_link", "additional_image_link",
                "price", "sale_price", "availability", "brand", "gtin", "item_group_id",
                "condition", "material", "size", "product_type", "google_product_category",
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
    for k in ("author", "age", "set", "material", "categorised", "format", "genre"):
        print(f"{k:17s}: {stats[k]} ({stats[k]*100//n}%)")
    print(f"wrote {xml_path}")
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
