# -*- coding: utf-8 -*-
"""Map every Books2Door product to the nav-menu collections it belongs to.

A failed request must never be recorded as an empty collection - the previous
run silently logged 142 throttled collections as having 0 products. Failures are
tracked separately and retried, and concurrency is kept low enough not to trip
the store's rate limiting.
"""
import io, json, sys, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = 'https://www.books2door.com'
SKIP = {'all', 'all-products-in-stock'}      # 'everything' is not a category

handles = [h for h in json.load(io.open('nav_handles.json', encoding='utf-8')) if h not in SKIP]
titles = {c['handle']: c['title'] for c in json.load(io.open('collections.json', encoding='utf-8'))}

lock = threading.Lock()
member, sizes, failed, done = {}, {}, [], [0]


def get(url):
    """Return parsed JSON, or raise so the caller can tell failure from empty."""
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'b2d-feed-audit/1.0'})
            return json.loads(urllib.request.urlopen(req, timeout=90).read())
        except Exception as e:
            last = e
            time.sleep(3 * (attempt + 1))     # 3s, 6s, 9s, 12s
    raise RuntimeError('%s -> %s' % (url, str(last)[:70]))


def crawl(h):
    title = titles.get(h, h)
    page, got, local = 1, 0, []
    try:
        while page <= 30:
            d = get('%s/collections/%s/products.json?limit=250&page=%d' % (BASE, h, page))
            prods = d.get('products', [])
            if not prods:
                break
            for p in prods:
                for v in p.get('variants', []):
                    local.append(str(v['id']))
            got += len(prods)
            page += 1
            time.sleep(0.4)
    except Exception as e:
        with lock:
            failed.append((h, title, str(e)[:80]))
            done[0] += 1
            print('%3d/%d  FAILED %-44s %s' % (done[0], len(handles), title[:44], str(e)[:50]),
                  flush=True)
        return
    with lock:
        for vid in local:
            member.setdefault(vid, set()).add(title)
        sizes[title] = got
        done[0] += 1
        print('%3d/%d  %-50s %5d' % (done[0], len(handles), title[:50], got), flush=True)


with ThreadPoolExecutor(max_workers=4) as ex:
    list(ex.map(crawl, handles))

# one serial retry pass for anything that failed
if failed:
    print('\nretrying %d failed collections serially...' % len(failed), flush=True)
    retry = [h for h, _, _ in failed]
    failed.clear()
    for h in retry:
        crawl(h)

json.dump({k: sorted(v) for k, v in member.items()},
          io.open('membership.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(sizes, io.open('collection_sizes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(failed, io.open('failed.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('\nDONE - variants mapped: %d, collections ok: %d, still failing: %d'
      % (len(member), len(sizes), len(failed)))
