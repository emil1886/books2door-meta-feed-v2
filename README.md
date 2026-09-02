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
| Set / no. books | `custom_label_4`    |
| Binding         | `g:material`        |

`g:material` carries exactly three values - **Paperback**, **Hardback**,
**Board Book** - collapsed from the 15 binding spellings the source uses
(Sprayed Edges Hardback, Leather Bound, Flexibound, Hardcover and so on, plus
two misspellings, `Hardabck` and `Hardaback`). A mixed binding takes the first
listed, so `Paperback/Hardback` reads as Paperback. Anything that is not a book
- Educational Toys, Yoga Cards - gets no material rather than a wrong one.

Because binding moved out, **`g:product_type` is now byte-identical to the
DataFeedWatch value** (`Fiction`, `9-14`, `B2D DEALS`, ...). Note that crumb is
not a single taxonomy: it mixes genre, age band and merchandising bucket, so a
product is filed under one of the three, never consistently. Use
`custom_label_1` for age-based product sets rather than product_type.

Genre (Fiction / Non-Fiction) is deliberately dropped - it was judged
unimportant for this feed, and 1,760 of the 1,861 genre-tagged items already
stated it in their product_type crumb anyway.

`custom_label_2` / `custom_label_3` are Books2Door promo tags and are passed
through untouched. `id`, `price`, `sale_price`, `link`, `gtin`, `item_group_id`
and all images are copied verbatim - this feed never invents commercial data.

Example:

    before  Alex Rider (Book 12-14) by Anthony Horowitz: 3 Books Collection Set - Ages 9-12 - Paperback
    after   Alex Rider (Book 12-14)
            custom_label_0=Anthony Horowitz  custom_label_1=Ages 9-12
            custom_label_4=3 Books Collection Set
            material=Paperback   product_type=Fiction

No title may mention an age, Paperback, Hardback or a binding: those are stripped
wherever they appear, not just at the end. Source titles are wildly inconsistent
('Ages 0-5- Paperback', 'Backpack- Ages 1-7', 'Paperback (With A Free Audiobook)',
'Fiction/Non Fiction'), so the parser finds each detail wherever it sits and
excises it rather than peeling segments off the end.

## Run it

    python build_feed.py --out-dir docs --review-csv review_titles.csv

`--min-products 3500` aborts the build rather than publishing a truncated feed.

The GitHub Action rebuilds daily at 06:00 UTC and deploys `docs/` to Pages,
committing the rebuilt feed to `main` as a history snapshot.

If the schedule ever goes sub-daily, make that commit conditional first: it
costs ~1.3 MB compressed per run, so hourly would add roughly 11 GB a year.
Pages serves the artifact built during the run, so it does not need the commit.
