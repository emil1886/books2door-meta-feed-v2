# Books2Door Meta feed v2 - clean titles

## Feed URL

    https://emil1886.github.io/books2door-meta-feed-v2/b2d-claude-feed.xml

Intended final URL, once DNS is in place:

    https://feeds.anicca.co.uk/b2d-claude-feed.xml

That needs a CNAME record for `feeds.anicca.co.uk` pointing at
`emil1886.github.io`, then the custom domain set on this repo's Pages settings.
Do NOT set the custom domain before the DNS record resolves - Pages redirects
the github.io URL to the custom domain as soon as it is set, so the feed would
be unreachable at both addresses until DNS caught up.

`feed.xml` and `books2door_meta_feed_v2.xml` are still published as copies so
URLs already handed out keep working. They are build-time copies only, kept out
of git. Drop the ones nothing points at.


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

## Categories are not this feed's job

Books2Door handles them upstream in DataFeedWatch, which emits them as repeated
`<internal_label>` tags. Those pass through untouched, and `g:product_type` is
left byte-identical to the source.

This feed used to build a category path in `product_type` from that same data.
That work is removed as of 2026-09-16 - see the git history if it is ever needed
again. Note `internal_label` is not namespaced, unlike most fields here.

## Currency

`price` and `sale_price` carry the ISO code: `85.99 GBP`.

DataFeedWatch sends bare decimals, and Meta rejects those as "missing the field
currency" on every product. Meta wants the **code**, not the symbol, so this is
`GBP` rather than `£`.

The numeric value is never altered, only the unit stated, and the catalogue total
is unchanged. Verified against the live books2door.com storefront: feed prices
match exactly, so GBP is right and no conversion is involved.

This was briefly reverted on 2026-10-05 after a doubled `£` appeared. The feed
was clean throughout - 4,156 prices with `GBP`, zero with a `£`, none with both -
and the doubling turned out to come from another platform. Re-enabled 2026-10-06.
`--currency` overrides, or set it empty to switch it off.

## Schedule

Two runs a day, 06:00 and 20:00 UTC.

GitHub defers scheduled workflows under load - these were firing five to eight
hours late and 06 October missed entirely, leaving the feed 15 hours behind the
source. Two attempts mean a deferred run is not a lost day, and the evening slot
also catches DataFeedWatch's late refreshes, which have landed as late as 18:23.

Only the morning run commits. Pages serves the artifact built during the run, so
the commit is just a history snapshot; at ~1.3 MB compressed, committing on both
runs would add roughly 0.9 GB a year.

## Run it

    python build_feed.py --out-dir docs --review-csv review_titles.csv

**The sub-£10 price filter lives upstream in DataFeedWatch, not here.** This
feed does not duplicate it.

It is worth knowing what that upstream filter reads, though. DataFeedWatch
applies it to `rrp`, and `rrp` in this source holds the **sale price**, not the
recommended retail price - equal to `sale_price` on 3,972 of 3,974 products on
2026-11-24, equal to `price` on only 13. So it drops heavily discounted books
whose real RRP is well over £10: on that day's data it removed 1,090 products
where a full-price floor removes 367, excluding 723 wrongly (*RHS Gardening
Through the Year*, full £20.00, on sale at £7.99). Fixing that means repointing
the filter at the full price in DataFeedWatch, or correcting the `rrp` mapping
there.

`--min-full-price 10` applies the correct version here instead, on `g:price`,
if that upstream fix is ever impractical. It is off by default.

**The build refuses to publish a sudden drop in product count.** Two guards,
both on the published count rather than the source:

- `--max-shrink` (default 0.15) compares against the last feed published, read
  from `docs/`. More than a 15% fall and the build refuses. This is the guard
  that matters, and it re-baselines itself, so it needs no retuning when the
  catalogue grows, shrinks or a filter changes.
- `--min-products` (default 1000) is only an absolute backstop for a
  catastrophically empty feed.

When a drop is intended - a new filter, say - the error names the exact flag to
re-run with once to accept it and re-baseline.

The absolute floor used to be the only guard, sized near the real catalogue at
3,500. On 2026-11-25 an upstream filter removed a quarter of the products and
every run failed, which is why the sizing moved to a relative check.

When that guard trips, the build waits 30 minutes and tries again, up to four
attempts over 90 minutes - DataFeedWatch serves a short feed mid-refresh (2,921
items on 25 Nov) and it clears itself once the refresh completes. If all four
fail the run errors and the previously published feed stays live, untouched.
Tune with `ATTEMPTS` and `RETRY_WAIT_SECONDS` on that step.

The GitHub Action rebuilds daily at 06:00 UTC and deploys `docs/` to Pages,
committing the rebuilt feed to `main` as a history snapshot.

If the schedule ever goes sub-daily, make that commit conditional first: it
costs ~1.3 MB compressed per run, so hourly would add roughly 11 GB a year.
Pages serves the artifact built during the run, so it does not need the commit.
