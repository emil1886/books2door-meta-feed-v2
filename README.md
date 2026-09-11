# Books2Door Meta feed v2 - clean titles

A **derived** Meta catalogue feed for Books2Door. It does not touch Shopify.

    Shopify  ->  DataFeedWatch (shop 30774)  ->  [this repo]  ->  Meta catalogue
                          ^ source of truth        ^ re-titles only

## What it changes

`g:title` becomes the **product name alone**. Everything the old title crammed in
moves to structured fields:

| Detail          | Goes to             |
|-----------------|---------------------|
| Author          | `custom_label_0`    |
| Age             | `custom_label_1`    |
| Binding         | `g:material`        |
| Pack quantity   | `g:size`            |

`g:material` carries exactly three values - **Paperback**, **Hardback**,
**Board Book** - collapsed from the 15 binding spellings the source uses
(Sprayed Edges Hardback, Leather Bound, Flexibound, Hardcover and so on, plus
two misspellings, `Hardabck` and `Hardaback`). A mixed binding takes the first
listed. Anything that is not a book gets no material rather than a wrong one.

`g:size` carries the pack quantity as `3 Books`, `4 Books` and so on, on 2,849
products. Every pack phrase the parser recognises states "book(s)", so the unit
is always accurate. Singles simply have no size.

Because binding moved out, **`g:product_type` is byte-identical to the
DataFeedWatch value** (`Fiction`, `9-14`, `B2D DEALS`, ...). That crumb is not a
single taxonomy: it mixes genre, age band and merchandising bucket, so a product
is filed under one of the three, never consistently. Use `custom_label_1` for
age-based product sets rather than product_type. The `>` hierarchy in
product_type is free if sub-categories are ever wanted.

Genre (Fiction / Non-Fiction) is deliberately dropped - it was judged
unimportant for this feed, and 1,760 of the 1,861 genre-tagged items already
stated it in their product_type crumb anyway.

**Each field carries exactly one meaning.** On 2026-09-02 DataFeedWatch began
populating `custom_label_0` with the site category - the slot this feed uses for
the author. A leftover source value would make the label mean different things on
different rows, so where we have no value of our own the field is removed.

With pack quantity moved to `g:size`, `custom_label_4` is DataFeedWatch's again
and passes straight through. Note its content is 97% unique per product (SKU
ranges like `B2D8088-B2D8084`), so it is not usable for product sets.

`custom_label_2` / `custom_label_3` are Books2Door promo tags and are passed
through untouched. `id`, `price`, `sale_price`, `link`, `gtin`, `item_group_id`
and all images are copied verbatim - this feed never invents commercial data.

Example:

    before  Alex Rider (Book 12-14) by Anthony Horowitz: 3 Books Collection Set - Ages 9-12 - Paperback
    after   Alex Rider (Book 12-14)
            custom_label_0=Anthony Horowitz  custom_label_1=Ages 9-12
            material=Paperback   size=3 Books   product_type=Fiction

No title may mention an age, Paperback, Hardback or a binding: those are stripped
wherever they appear, not just at the end. Source titles are wildly inconsistent
('Ages 0-5- Paperback', 'Backpack- Ages 1-7', 'Paperback (With A Free Audiobook)',
'Fiction/Non Fiction'), so the parser finds each detail wherever it sits and
excises it rather than peeling segments off the end.

## Website categories

`g:product_type` carries the categories a product sits in on books2door.com,
labelled as the shopper sees them in the nav dropdowns:

    7-9 > Book Collections > Kids' Books > New Kids Books

DataFeedWatch's own crumb stays first so existing product sets keep matching.
Meta matches any level of the path with "contains". Coverage is 98% of products,
a median of 3 categories each, longest path 642 characters against a 750 limit.

**Membership is live.** DataFeedWatch lists every Shopify collection a product
belongs to, and the build reads it, keeps only collections in the site nav, and
writes them into `product_type`. New products are categorised the day they
appear - there is no crawl and nothing cached about which product is in what.

DataFeedWatch has changed the shape of this twice, so the build reads both:
repeated `<internal_label>` tags (current, and note it is *not* namespaced, like
`rrp` and `perc_off`), falling back to a second `<g:product_type>` holding a
`;`-separated list (older). Without that fallback an upstream change silently
empties the category field - which is exactly what happened on 2026-09-10.

`data/nav_categories.json` holds the naming and the exclusions - never
membership:

* **collection title -> nav label** for the 161 collections in the site nav.
  They differ, and the label is what the shopper recognises: *Bestselling Books
  - Top 200* is shown as "Books2Door Top 100", *Books for Ages 9-14* as
  "Ages 9-12+". Everything else keeps its own collection title.
* **parents** - 26 collections sitting on more than half the catalogue, so they
  filter nothing: All, Core Products, Top Authors, Top Publishers, Genres &
  Types, Series, Books By Age, Bestselling Books and similar.
* **excluded** - 46 price bands and internal bookkeeping: Books for £10-£15,
  Bestseller Books £5 - £10, B2D Listed Books, B2D Stocked Books, Brands.

Everything else becomes a crumb - 594 categories in all. An earlier version kept
only collections found in the site nav, which silently cost 464 real
subcategories: publisher collections (Penguin Books, Hachette Books), genres
(Fantasy Books), seasonal picks (Summer Reads) and age refinements (New Books
for Kids - Ages 8-12+). The nav's dropdown markup carries only the top level,
not the children of Top Publishers or Genres & Types, so scraping it was never
going to find them.

Refresh the label map when the site nav changes:

    python refresh_nav_labels.py

The 750-character truncation that affected 81 products under the old shape is
gone - repeated tags have no such cap. Longest path is now 304 characters.

`internal_label` is not a field Meta reads, so it is carried through untouched
but does nothing on its own. The categories reach Meta because they are written
into `product_type`, which Meta does read.

## Run it

    python build_feed.py --out-dir docs --review-csv review_titles.csv

`--min-products 3500` aborts the build rather than publishing a truncated feed.

The GitHub Action rebuilds daily at 06:00 UTC and deploys `docs/` to Pages,
committing the rebuilt feed to `main` as a history snapshot.

If the schedule ever goes sub-daily, make that commit conditional first: it
costs ~1.3 MB compressed per run, so hourly would add roughly 11 GB a year.
Pages serves the artifact built during the run, so it does not need the commit.
