import json,re,glob,html
exec(open('so_extract.py').read().split('rows=[]')[0].replace("items=json.load(open('so_all.json'))",""))
items=json.load(open('so_all.json'))
rows=json.load(open('so_rows.json'))
by={r['slug']:r for r in rows}

PAGE_NOISE=re.compile(r'(^|\.)(standoff365\.com|mindbox\.ru|ptsecurity\.com/en/standoff|'
 r'jquery\.com|nextjs\.org|vercel\.app|gstatic\.com|cloudflare\.com)$',re.I)

for f in glob.glob('sopg/*.html'):
    slug=f.split('/')[1].rsplit('.',3)[0]
    if slug not in by: continue
    raw=open(f,encoding='utf-8',errors='replace').read()
    # the Next.js payload holds description as escaped JSON strings
    txt=html.unescape(raw).replace('\\n','\n').replace('\\"','"').replace('\\u002F','/')
    # limit to the description-ish region to avoid framework noise
    m=re.search(r'"description":"(.*?)","specialRules"',txt,re.S)
    chunks=[m.group(1)] if m else []
    m2=re.search(r'"shortDescription":"(.*?)"',txt,re.S)
    if m2: chunks.append(m2.group(1))
    for c in chunks:
        for d in extract(c):
            if PAGE_NOISE.search(d.lstrip('*.')): continue
            if d not in by[slug]['scope_domains']:
                by[slug]['scope_domains'].append(d)

from collections import Counter
for r in rows:
    if r['scope_domains'] and not r['primary_domain']:
        r['primary_domain']=Counter(reg(d) for d in r['scope_domains']).most_common(1)[0][0]
json.dump(rows,open('so_rows.json','w'),ensure_ascii=False,indent=1)
print('programs',len(rows))
print('with domains',sum(1 for r in rows if r['scope_domains']))
print('unique scope entries',len({d for r in rows for d in r['scope_domains']}))
print('unique root domains',len({reg(d) for r in rows for d in r['scope_domains']}))
