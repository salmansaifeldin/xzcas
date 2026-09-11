import json,re,urllib.request,time
from concurrent.futures import ThreadPoolExecutor
progs=[p for p in json.load(open('programs.json')) if p['id'].startswith('YesWeHack:')]
SKIP=re.compile(r'yeswehack|w3\.org|schema\.org|github\.com|google|gstatic|cloudflare|twitter\.com|x\.com|linkedin|youtube|wikipedia|example\.com|owasp|cve\.org|mitre|hackerone|bugcrowd',re.I)
def get(p):
    s=p['id'].split(':',1)[1]
    try:
        r=urllib.request.Request('https://api.yeswehack.com/programs/'+s,headers={'User-Agent':'Mozilla/5.0'})
        d=json.loads(urllib.request.urlopen(r,timeout=45).read())
    except Exception as e:
        return (p['id'],p['name'],[],str(e))
    txt=(d.get('rules') or '')
    doms=[]
    for m in re.finditer(r'(?:https?://|\*\.|\b)([a-z0-9][a-z0-9.-]*\.(?:com|io|net|org|dev|co|ai|app|xyz|cloud|eu|fr|de|uk|us|tech|se|nl|be|ch|es|it|jp|kr|in|cn|me|info|biz|gg|sh|to|ly|so))\b',txt,re.I):
        dm=m.group(1).lower().strip('.')
        if not SKIP.search(dm): doms.append(dm)
    seen=[];
    for x in doms:
        if x not in seen: seen.append(x)
    scopes=[sc.get('scope') for sc in (d.get('scopes') or [])]
    return (p['id'],p['name'],seen[:8],scopes)
with ThreadPoolExecutor(5) as ex: res=list(ex.map(get,progs))
json.dump(res,open('ywh_res.json','w'),indent=1)
print('total',len(res),'with dom',sum(1 for r in res if r[2]))
for r in res[:5]: print(r[1],'->',r[2][:4])
