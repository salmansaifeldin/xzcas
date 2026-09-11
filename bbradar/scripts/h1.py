import json,urllib.request,time
from concurrent.futures import ThreadPoolExecutor
progs=[p for p in json.load(open('programs.json')) if p['id'].startswith('HackerOne:')]
Q='query($h:String!){team(handle:$h){handle name website url state}}'
def get(p):
    h=p['id'].split(':',1)[1]
    body=json.dumps({'query':Q,'variables':{'h':h}}).encode()
    for a in range(3):
        try:
            r=urllib.request.Request('https://hackerone.com/graphql',data=body,
              headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0','Accept':'application/json'})
            d=json.loads(urllib.request.urlopen(r,timeout=45).read())
            t=(d.get('data') or {}).get('team') or {}
            return (p['id'],p['name'],t.get('website'),t.get('name'))
        except Exception as e:
            time.sleep(2*(a+1))
    return (p['id'],p['name'],None,None)
with ThreadPoolExecutor(6) as ex: res=list(ex.map(get,progs))
json.dump(res,open('h1.json','w'),indent=1)
print('total',len(res),'with website',sum(1 for r in res if r[2]))
