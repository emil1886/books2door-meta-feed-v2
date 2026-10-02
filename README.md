# Anicca Meta feeds

Two client product feeds for Meta Commerce Manager, built daily and served from
one GitHub Pages site. They share a repo because a Pages site allows only one
deployment at a time - two repos deploying to one domain would race.

## Feed URLs

Intended final form, once DNS is in place:

    https://feeds.anicca.co.uk/b2d-claude-feed.xml      Books2Door
    https://feeds.anicca.co.uk/gt-claude-feed.xml       Golden Tours

Working today:

    https://emil1886.github.io/books2door-meta-feed-v2/b2d-claude-feed.xml
    https://emil1886.github.io/books2door-meta-feed-v2/gt-claude-feed.xml

`feeds.anicca.co.uk` needs a CNAME record pointing at `emil1886.github.io`,
after which the custom domain is set on this repo's Pages settings. Do NOT set
the custom domain first - Pages redirects the github.io URL to the custom domain
as soon as it is set, so the feeds would be unreachable at both addresses until
DNS caught up.

Older filenames are still published as build-time copies so URLs already handed
out keep working: `feed.xml`, `books2door_meta_feed_v2.xml` and
`goldentours_meta_feed.xml`. Drop the ones nothing points at.

## The two builds are independent

Either may fail without taking the other down. The canonical feed files are
committed, so a failed build republishes yesterday's file unchanged - stale
rather than empty, which is the safer failure for a live catalogue. The workflow
refuses to deploy if either feed is missing or implausibly small.

| | Books2Door | Golden Tours |
|---|---|---|
| source | the DataFeedWatch feed | crawls goldentours.com |
| script | `build_feed.py` + `parse_titles.py` | `goldentours_meta_feed_gbp.py` |
| job | rewrites titles | builds the whole feed, incl. images |

The old `emil1886/goldentours-meta-feed` repo still builds and publishes its own
URL, so nothing there breaks during the move. That means Golden Tours is crawled
twice a day until you retire it - disable its workflow once Meta points here.

## Books2Door - what this feed changes

## Categories are not this feed's job

Books2Door handles them upstream in DataFeedWatch, which emits them as repeated
`<internal_label>` tags. Those pass through untouched, and `g:product_type` is
left byte-identical to the source.

This feed used to build a category path in `product_type` from that same data.
That work is removed as of 2026-09-16 - see the git history if it is ever needed
again. Note `internal_label` is not namespaced, unlike most fields here.

## Run it

    python build_feed.py --out-dir docs --review-csv review_titles.csv

`--min-products 3500` aborts the build rather than publishing a truncated feed.

The GitHub Action rebuilds daily at 06:00 UTC and deploys `docs/` to Pages,
committing the rebuilt feed to `main` as a history snapshot.

If the schedule ever goes sub-daily, make that commit conditional first: it
costs ~1.3 MB compressed per run, so hourly would add roughly 11 GB a year.
Pages serves the artifact built during the run, so it does not need the commit.
