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
| Format          | `product_type` tail |

Genre (Fiction / Non-Fiction) is deliberately dropped - it was judged unimportant
for this feed, and 1,760 of the 1,861 genre-tagged items already stated it in
their original DataFeedWatch `product_type` crumb anyway. Format keeps no label
for the same reason, but survives as the last `product_type` crumb because 30
items are otherwise indistinguishable (same title, different binding).

`custom_label_2` / `custom_label_3` are Books2Door promo tags and are passed
through untouched. `id`, `price`, `sale_price`, `link`, `gtin`, `item_group_id`
and all images are copied verbatim - this feed never invents commercial data.

Example:

    before  Alex Rider (Book 12-14) by Anthony Horowitz: 3 Books Collection Set - Ages 9-12 - Paperback
    after   Alex Rider (Book 12-14)
            custom_label_0=Anthony Horowitz  custom_label_1=Ages 9-12
            custom_label_4=3 Books Collection Set
            product_type=Fiction > Paperback

## Run it

    python build_feed.py --out-dir docs --review-csv review_titles.csv

`--keep-set-in-title` leaves "3 Books Collection Set" in the name; by default it
is stripped, because it now has its own label.
`--min-products 3500` aborts the build rather than publishing a truncated feed.

The GitHub Action rebuilds daily at 06:00 UTC and deploys `docs/` to Pages.
