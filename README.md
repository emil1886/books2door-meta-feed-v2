# Books2Door Meta feed v2 - clean titles

A **derived** Meta catalogue feed for Books2Door. It does not touch Shopify.

    Shopify  ->  DataFeedWatch (shop 30774)  ->  [this repo]  ->  Meta catalogue
                          ^ source of truth        ^ re-titles only

## What it changes

`g:title` becomes the **product name alone**. Everything the old title crammed in
moves to structured fields:

| Detail  | Goes to             |
|---------|---------------------|
| Author  | `custom_label_0`    |
| Format  | `custom_label_1`    |
| Age     | `custom_label_4`    |
| Genre   | `product_type` path |

`custom_label_2` / `custom_label_3` are Books2Door promo tags and are passed
through untouched. `id`, `price`, `sale_price`, `link`, `gtin`, `item_group_id`
and all images are copied verbatim - this feed never invents commercial data.

Example:

    before  Alex Rider (Book 12-14) by Anthony Horowitz: 3 Books Collection Set - Ages 9-12 - Paperback
    after   Alex Rider (Book 12-14): 3 Books Collection Set
            custom_label_0=Anthony Horowitz  custom_label_1=Paperback  custom_label_4=Ages 9-12
            product_type=Fiction > Ages 9-12 > Paperback

## Run it

    python build_feed.py --out-dir docs --review-csv review_titles.csv

`--strip-set-from-title` also removes "3 Books Collection Set" from the name.
`--min-products 3500` aborts the build rather than publishing a truncated feed.

The GitHub Action rebuilds daily at 06:00 UTC and deploys `docs/` to Pages.
