# -*- coding: utf-8 -*-
"""Books2Door Meta feed v2 - clean titles.

Source of truth: the existing DataFeedWatch Meta feed (read-only).
This script re-titles each item so g:title is the product name alone, and
puts author and age into custom labels, binding into g:material and pack
quantity into g:size - the details the old titles crammed in.

It also stamps the ISO currency onto price and sale_price - DataFeedWatch sends
bare decimals, which Meta rejects as "missing the field currency". The numeric
value is never altered, only the unit stated, and the prices are verified against
the UK storefront so GBP is correct.

Categories are NOT this feed's job. Books2Door handles them upstream in
DataFeedWatch via <internal_label>, which passes through untouched, so
g:product_type is left exactly as the source sends it.
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


def add_currency(item, tag, currency):
    """Append the ISO currency to a price, e.g. '47.94' -> '47.94 GBP'.

    DataFeedWatch sends bare decimals, which Meta reports as "missing the field
    currency" on every product. Returns True if it changed the field. The value
    itself is never touched - only the unit is stated - and a price that already
    names a currency, or is not a plain number, is left alone.
    """
    raw = gtext(item, tag)
    if not raw or re.search(r"[A-Za-z]", raw):
        return False
    try:
        float(raw.replace(",", ""))
    except ValueError:
        return False                      # not a plain number: leave it be
    gset(item, tag, f"{raw} {currency}")
    return True


def published_count(path):
    """Item count of the feed we last published, or 0 if there isn't one.

    The repository commits docs/ each morning, so checkout gives the build the
    previous feed to compare against. A missing or unreadable file means no
    baseline, and the relative guard simply does not apply.
    """
    if not os.path.exists(path):
        return 0
    try:
        channel = ET.parse(path).getroot().find("channel")
        return len(channel.findall("item")) if channel is not None else 0
    except ET.ParseError:
        return 0


def price_value(raw):
    """Numeric value of a price field, tolerating a currency suffix or commas."""
    m = re.match(r"\s*([0-9][0-9,]*(?:\.[0-9]+)?)", raw or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def drop_cheap(channel, floor):
    """Remove products whose FULL price is under the floor. Returns the count.

    This has to read g:price, not rrp. DataFeedWatch's rrp field tracks
    sale_price rather than the recommended retail price - they were equal on
    3,972 of 3,974 products on 2026-11-24, while rrp matched price on only 13 -
    so filtering on rrp drops heavily discounted books whose real RRP is well
    over the floor. On that day's data an rrp floor removed 1,090 products where
    a full-price floor removes 367, so 723 were being excluded wrongly.

    A product with a missing or unparseable price is kept, not silently dropped.
    """
    if not floor or floor <= 0:
        return 0
    removed = 0
    for item in list(channel.findall("item")):
        value = price_value(gtext(item, "price"))
        if value is not None and value < floor:
            channel.remove(item)
            removed += 1
    return removed


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=SOURCE_URL)
    ap.add_argument("--out-dir", default="docs")
    ap.add_argument("--basename", default="books2door_meta_feed_v2")
    ap.add_argument("--min-products", type=int, default=1000,
                    help="Absolute backstop on the PUBLISHED count. Deliberately "
                         "low - it only catches a catastrophically empty feed. "
                         "Sizing it near the real catalogue is what broke on "
                         "2026-11-25, so --max-shrink is the real guard.")
    ap.add_argument("--max-shrink", type=float, default=0.15,
                    help="Refuse to publish if the count drops more than this "
                         "fraction below the last published feed (0.15 = 15%%). "
                         "Self-calibrating, so it needs no retuning when the "
                         "catalogue or a filter changes. 0 disables.")
    ap.add_argument("--min-full-price", type=float, default=0.0,
                    help="Drop products whose full price (g:price) is under this. "
                         "OFF by default: the price filter belongs upstream in "
                         "DataFeedWatch, which already applies one, and this feed "
                         "does not duplicate it. Kept available because DFW's "
                         "filter reads rrp, which here holds the SALE price - set "
                         "this to 10 to filter on the true full price instead.")
    ap.add_argument("--currency", default="GBP",
                    help="ISO 4217 code appended to price and sale_price. Meta wants "
                         "the code, not the symbol, so GBP rather than £. Briefly "
                         "reverted on 2026-10-05 over a doubled symbol, which turned "
                         "out to come from another platform, not this feed.")
    ap.add_argument("--review-csv", default="")
    args = ap.parse_args()

    raw = fetch(args.source)
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        sys.exit("ERROR: no <channel> in source feed")
    source_count = len(channel.findall("item"))
    cheap = drop_cheap(channel, args.min_full_price)
    items = channel.findall("item")

    # Two guards, both on what we are about to PUBLISH rather than on the source,
    # so an over-eager filter cannot quietly ship a thin catalogue either.
    context = (f"{len(items)} to publish, {source_count} from source"
               + (f", {cheap} under £{args.min_full_price:g} full price" if cheap else ""))

    # 1. Absolute backstop. Deliberately low - it only catches a catastrophically
    #    empty feed. Sizing it near the real catalogue is what broke on 25 Nov:
    #    a floor of 3,500 set when the catalogue was ~4,200 failed every run once
    #    a filter removed a quarter of it.
    if len(items) < args.min_products:
        sys.exit(f"ERROR: {context} - below the absolute floor of "
                 f"{args.min_products} - refusing to publish")

    # 2. Relative guard, which is the one that actually earns its keep. It
    #    compares against the last feed we published, so it re-baselines itself
    #    and needs no retuning when the catalogue or a filter changes. A genuine
    #    mid-refresh truncation shows up as a sudden drop at any absolute size.
    previous = published_count(os.path.join(args.out_dir, args.basename + ".xml"))
    if previous and args.max_shrink > 0:
        allowed = previous * (1 - args.max_shrink)
        if len(items) < allowed:
            drop_pct = (1 - len(items) / previous) * 100
            sys.exit(
                f"ERROR: {context} - that is {drop_pct:.0f}% fewer than the "
                f"{previous} last published, over the {args.max_shrink * 100:.0f}% "
                f"limit. Refusing to publish.\n"
                f"       If this drop is intended (a new filter, say), re-run once "
                f"with --max-shrink {min(0.95, drop_pct / 100 + 0.05):.2f} to accept "
                f"it and re-baseline.")
        print(f"shrink check     : {len(items)} vs {previous} last published "
              f"({(len(items) / previous - 1) * 100:+.1f}%)")

    review, stats = [], {"author": 0, "format": 0, "age": 0, "genre": 0, "set": 0,
                         "material": 0, "priced": 0, "changed": 0}
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

        # Without this Meta reports every product as missing the field currency.
        if args.currency:
            for tag in ("price", "sale_price"):
                if add_currency(item, tag, args.currency) and tag == "price":
                    stats["priced"] += 1

        if new_title != orig_title:
            stats["changed"] += 1

        review.append({"id": gtext(item, "id"), "old_title": orig_title, "new_title": new_title,
                       "author": p["author"], "format": p["format"], "age": p["age"],
                       "genre": p["genre"], "material": material, "set": p["pack"],
                       "pack_count": p["pack_count"],
                       "product_type": gtext(item, "product_type")})

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
    print(f"source items     : {source_count}")
    print(f"dropped <£{args.min_full_price:g} full price : {cheap}")
    print(f"published items  : {n}")
    print(f"titles rewritten : {stats['changed']} ({stats['changed']*100//n}%)")
    for k in ("author", "age", "set", "material", "priced", "format", "genre"):
        print(f"{k:17s}: {stats[k]} ({stats[k]*100//n}%)")
    print(f"wrote {xml_path}")
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
