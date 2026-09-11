import json,re,socket,unicodedata,urllib.request,ssl
from concurrent.futures import ThreadPoolExecutor
rows=json.load(open('final.json'))
miss=[r for r in rows if not r['domain']]
print('missing',len(miss))
STOP=set('''public private bug bounty program programme vdp managed engagement mbb audit competition boost
ongoing disclosure vulnerability security research web api smart contract blackbox bbp the and of inc ltd llc
gmbh ag sa nv bv plc co corp company group holding technologies technology labs lab foundation network protocol
finance capital exchange app apps mobile android ios site website main core platform id gold cortex synapse'''.split())
def norm(s):
    s=unicodedata.normalize('NFKD',s.lower())
    return re.sub(r'[^a-z0-9]','',s)
def base(name):
    name=re.split(r'[|(\[\-–—:]',name)[0]
    toks=[t for t in re.split(r'[^A-Za-z0-9]+',name) if t]
    toks=[t for t in toks if t.lower() not in STOP and not re.fullmatch(r'\d+',t)]
    if not toks: return None
    joined=norm(''.join(toks))
    first=norm(toks[0])
    out=[]
    for c in (joined,first):
        if c and 2<len(c)<=30 and c not in out: out.append(c)
    return out
TLDS=['.com','.io','.co','.org','.net','.ai','.xyz','.app','.dev','.finance','.fi','.tech','.in','.ru','.fr','.de','.nl','.ch','.eu']
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
def resolves(d):
    try: socket.getaddrinfo(d,443); return True
    except: return False
def verify(d,tok):
    for u in ('https://'+d,'https://www.'+d):
        try:
            r=urllib.request.Request(u,headers={'User-Agent':UA})
            b=urllib.request.urlopen(r,timeout=12,context=ctx).read(120000).decode('utf-8','replace')
        except Exception: continue
        t=re.search(r'<title[^>]*>(.*?)</title>',b,re.S|re.I)
        title=norm(t.group(1)) if t else ''
        if tok in title or tok in norm(b[:6000]): return True
        return False
    return False
def work(r):
    cands=base(r['name']) or []
    for c in cands:
        for tld in TLDS:
            d=c+tld
            if not resolves(d): continue
            if verify(d,c):
                return (r['id'],d)
            break
    return (r['id'],None)
with ThreadPoolExecutor(12) as ex: res=list(ex.map(work,miss))
found={i:d for i,d in res if d}
print('inferred',len(found))
for r in rows:
    if not r['domain'] and r['id'] in found:
        r['domain']=found[r['id']]; r['source']='inferred'
json.dump(rows,open('final.json','w'),indent=1,ensure_ascii=False)
print('total now',sum(1 for r in rows if r['domain']),'/',len(rows))
