import json,re,unicodedata
from collections import Counter
items=json.load(open('so_all.json'))

NOISE=re.compile(r'(^|\.)(standoff365\.com|ptsecurity\.com/standoff|bugbounty\.standoff365\.com|'
 r'itunes\.apple\.com|apps\.apple\.com|play\.google\.com|google\.com|github\.com|githubusercontent\.com|'
 r't\.me|telegram\.org|vk\.cc/bug|twitter\.com|x\.com|youtube\.com|linkedin\.com|facebook\.com|'
 r'w3\.org|schema\.org|example\.com|owasp\.org|cve\.mitre\.org|mitre\.org|cvss\.js\.org|first\.org|'
 r'wikipedia\.org|habr\.com|medium\.com|docs\.google\.com|drive\.google\.com|forms\.gle|'
 r'mail\.google\.com|gmail\.com|yandex\.ru/support|microsoft\.com|apple\.com)$',re.I)
TLD=r'(?:ru|com|net|org|io|me|pro|info|biz|su|рф|dev|app|cloud|tech|online|store|site|link|cc|chat|team|digital|team|ai|bank|shop|kz|by|uz|ua|am|ge|tj|kg|md|az|fi|de|nl|uk|eu|co|tv|fm|one|life|group|center|company|agency|press|news|space|website|host|xyz|gg|sh|to)'
# domain token, allows leading *. and \*.
DOM=re.compile(r'(?<![\w@/.-])(\*\.|\\\*\.)?((?:[a-zA-Z0-9_-]{1,63}\.)+)('+TLD+r')(?![\w-])',re.I)
ALT=re.compile(r'(?<![\w@/.-])((?:[a-zA-Z0-9_-]{1,63}\.)+)\(([a-z|]{2,30})\)',re.I)

def clean(d):
    d=d.lower().strip('.').lstrip('*.').replace('\\','')
    return d

def extract(text):
    if not text: return []
    out=[]
    # expand name.(com|ru)
    def exp(m):
        head=m.group(1); tlds=m.group(2).split('|')
        return ' '.join(head+t for t in tlds)
    text=ALT.sub(exp,text)
    # drop markdown link targets that are just images
    for m in DOM.finditer(text):
        wild=bool(m.group(1))
        d=clean(m.group(2)+m.group(3))
        if d.count('.')<1: continue
        if NOISE.search(d): continue
        if re.match(r'^\d+\.\d+\.\d+\.\d+$',d): continue
        out.append(('*.'+d) if wild else d)
    seen=[]
    for x in out:
        if x not in seen: seen.append(x)
    return seen

def reg(d):
    d=d.lstrip('*.')
    p=d.split('.')
    if len(p)>=3 and p[-2] in ('co','com','org','net','gov','ac','edu'): return '.'.join(p[-3:])
    return '.'.join(p[-2:])

rows=[]
for i in items:
    text='\n'.join(str(i.get(k) or '') for k in ('description','shortDescription','specialRules','headerDescription'))
    doms=extract(text)
    prim=None
    if doms:
        c=Counter(reg(d) for d in doms)
        prim=c.most_common(1)[0][0]
    rows.append({
      'id':i['id'],'slug':i['slug'],'name':i['name'],'vendor':i.get('vendorName'),
      'status':i.get('status'),'finished':i.get('finished'),
      'url':f"https://bugbounty.standoff365.com/en-US/programs/{i['slug']}",
      'primary_domain':prim,'scope_domains':doms})
json.dump(rows,open('so_rows.json','w'),ensure_ascii=False,indent=1)
print('programs',len(rows))
print('with scope domains',sum(1 for r in rows if r['scope_domains']))
print('unique scope entries',len({d for r in rows for d in r['scope_domains']}))
for r in rows[:12]: print(' ',r['name'][:32],'|',r['primary_domain'],'|',len(r['scope_domains']))
