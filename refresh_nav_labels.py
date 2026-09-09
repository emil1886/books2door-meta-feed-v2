# -*- coding: utf-8 -*-
"""Nav dropdown label per collection handle - what the shopper actually sees."""
import io, re, sys, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
h = io.open('home.html', encoding='utf-8', errors='replace').read()
m = re.search(r'<header[\s\S]{0,400000}?</header>', h, re.I)
region = m.group(0) if m else h[:400000]
links = re.findall(
    r'href="(?:https://www\.books2door\.com)?/collections/([a-z0-9\-_%]+)"[^>]*>\s*([^<]{2,80}?)\s*<',
    region, re.I)
label = {}
for handle, text in links:
    text = re.sub(r'\s+', ' ', text).strip()
    if handle not in label and text:
        label[handle] = text
json.dump(label, io.open('nav_labels.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('nav labels captured: %d' % len(label))
for k in ['bestselling-books-top-200', 'uk-bestselling-books', '9-14', 'baby',
          'stem-books', 'childrens-teenage-young-adult-comic-strips-graphic-novels']:
    print('   %-56s -> %s' % (k, label.get(k, '(not in nav)')))
