import json,re,hashlib,os,html,unicodedata
progs=json.load(open('programs2.json'))
h1={r[0]:r[2] for r in json.load(open('h1.json'))}
ywh={r[0]:r[2] for r in json.load(open('ywh_res.json'))}

PLATFORM_HOSTS=set("""bbradar.io hackerone.com bugcrowd.com bugcrowdusercontent.com hackenproof.com hacken.io
immunefi.com intigriti.com standoff365.com bi.zone bugrap.io cantina.xyz sherlock.xyz inspectiv.com r.xyz
issuehunt.io compass-security.com bugbounty.ch gobugfree.com bugbase.ai auditone.io patchday.io certik.com
huntr.com hackzar.com yeswehack.com ptsecurity.com""".split())
NOISE=re.compile(r"""(^|\.)(w3\.org|schema\.org|google[a-z]*\.[a-z.]+|gstatic\.com|googleapis\.com|googletagmanager\.com|
cloudflare\.com|cloudflareinsights\.com|jsdelivr\.net|unpkg\.com|jquery\.com|fontawesome\.com|typekit\.net|
sentry\.io|bugsnag\.com|datadoghq\.com|amazonaws\.com|digitaloceanspaces\.com|imagedelivery\.net|cloudfront\.net|
twitter\.com|x\.com|t\.me|discord\.gg|discord\.com|linkedin\.com|facebook\.com|instagram\.com|youtube\.com|youtu\.be|
github\.com|github\.io|githubusercontent\.com|gitbook\.io|medium\.com|telegram\.org|reddit\.com|wikipedia\.org|
mozilla\.org|example\.com|owasp\.org|cve\.org|mitre\.org|nist\.gov|npmjs\.com|etherscan\.io|arbiscan\.io|
bscscan\.com|polygonscan\.com|basescan\.org|blockscout\.com|solscan\.io|explorer\.solana\.com|usercentrics\.eu|
yandex\.[a-z]+|yastatic\.net|yandexcloud\.net|mindbox\.ru|vercel\.app|netlify\.app|nuxt\.com|vuejs\.org|
react\.dev|apache\.org|json-ld\.org|purl\.org|creativecommons\.org|adobe\.com/go|hubspot\.com|hsforms\.com|
intercom\.io|intercomcdn\.com|zendesk\.com|calendly\.com|notion\.so|notion\.site|docsend\.com|figma\.com|
gravatar\.com|licdn\.com|fbcdn\.net|twimg\.com|cdninstagram\.com|vimeo\.com|loom\.com|substack\.com|
mailchimp\.com|sendgrid\.net|stripe\.com|paypal\.com|recaptcha\.net|hcaptcha\.com|cloudinary\.com|imgur\.com|
segment\.com|amplitude\.com|mixpanel\.com|hotjar\.com|clarity\.ms|bing\.com|microsoft\.com|windows\.net|
azureedge\.net|akamai[a-z]*\.net|fastly\.net|bootstrapcdn\.com|cdnjs\.com|polyfill\.io|ipify\.org|
whatsapp\.com|slack\.com|atlassian\.net|jira\.com|trello\.com|dropbox\.com|drive\.com|box\.com/shared)$""",
re.I|re.X)


EXTRA_NOISE=re.compile(r'''(^|\.)(atlassian\.com|atlassian\.net|google-analytics\.com|googleadservices\.com|
doubleclick\.net|hackerone-user-content\.com|apple\.com|play\.google\.com|firebounty\.com|hacking-lab\.com|
hexens\.io|immunefi\.foundation|cookieyes\.com|cdn-cookieyes\.com|freshdesk\.com|zealy\.io|kakao\.com|
gitlab\.com|bitbucket\.org|sourceforge\.net|stackoverflow\.com|npmjs\.org|pypi\.org|docker\.com|
onetrust\.com|cookiebot\.com|trustpilot\.com|glassdoor\.com/Overview|crunchbase\.com|
statuspage\.io|pendo\.io|fullstory\.com|newrelic\.com|optimizely\.com|launchdarkly\.com/docs|
wordpress\.org|squarespace\.com|wixstatic\.com|webflow\.io|ghost\.io|hackenproof\.com|
audits\.sherlock\.xyz|code4rena\.com|codehawks\.com|sherlock\.xyz|cyfrin\.io|spearbit\.com|
trailofbits\.com|consensys\.io|certora\.com|halborn\.com|quantstamp\.com|peckshield\.com|
slowmist\.com|chainsecurity\.com|zellic\.io|ottersec\.io|veridise\.com|guardianaudits\.com|
paladinsec\.co|sigmaprime\.io|nethermind\.io|dedaub\.com|blocksec\.com|beosin\.com|
salusec\.io|verilog\.solutions|zokyo\.io|shieldify\.org|pashov\.net|bailsec\.io|
statemind\.io|oxorio\.io|mixbytes\.io|decurity\.io|cantina\.xyz|cdnfonts\.com|linktr\.ee|datocms-assets\.com|yeswehack\.io|vk\.company\.ru|ftnscan\.com)$''',re.I|re.X)

def norm(s):
    s=unicodedata.normalize('NFKD',s.lower())
    return re.sub(r'[^a-z0-9]','',s)

def tokens(name):
    n=re.sub(r'\b(public|private|bug|bounty|program|programme|vdp|managed|engagement|mbb|audit|competition|'
             r'boost|ongoing|disclosure|vulnerability|security|research|web|api|smart|contract|blackbox|'
             r'bbp|the|and|of|inc|ltd|llc|gmbh|sa|ag|bb)\b','',name,flags=re.I)
    return [norm(t) for t in re.split(r'[^A-Za-z0-9]+',n) if len(norm(t))>=3]

URLRE=re.compile(r'https?://([a-zA-Z0-9][a-zA-Z0-9.-]{1,80}\.[a-zA-Z]{2,24})(?![a-zA-Z])')
def candidates(text):
    c={}
    for m in URLRE.finditer(text):
        d=m.group(1).lower().rstrip('.')
        if d.count('.')<1: continue
        base='.'.join(d.split('.')[-2:])
        if base in PLATFORM_HOSTS or d in PLATFORM_HOSTS: continue
        if any(d.endswith(h) for h in PLATFORM_HOSTS): continue
        if NOISE.search(d) or EXTRA_NOISE.search(d): continue
        if re.match(r'^\d+\.\d+',d): continue
        c[d]=c.get(d,0)+1
    return c

def reg(d):
    parts=d.split('.')
    if len(parts)>=3 and parts[-2] in ('co','com','org','net','gov','ac','edu'): return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])

rows=[]
for p in progs:
    dom=None; src=None
    if p['platform']=='HackerOne' and h1.get(p['id']):
        w=h1[p['id']]
        m=re.match(r'^(?:https?://)?([^/]+)',w.strip())
        if m:
            d=m.group(1).lower()
            if not NOISE.search(d) and '.' in d: dom=d; src='hackerone'
    if not dom:
        f='plat/'+hashlib.md5(p['platform_url'].encode()).hexdigest()+'.html'
        txt=''
        if os.path.exists(f):
            txt=html.unescape(open(f,encoding='utf-8',errors='replace').read())
        cands=candidates(txt)
        if p['platform']=='YesWeHack':
            for d in ywh.get(p['id'],[]) or []: cands[d]=cands.get(d,0)+3
        toks=tokens(p['name'])
        def score(item):
            d,n=item; r=reg(d); rb=norm(r.split('.')[0])
            s=0
            for t in toks:
                if t==rb: s+=100
                elif t in rb or rb in t: s+=60
            if d==r: s+=15
            if d.startswith('www.'): s+=12
            if d.startswith('docs.') or d.startswith('blog.'): s-=8
            return (s,n)
        if cands:
            best=max(cands.items(),key=score)
            if score(best)[0]>0:
                dom=reg(best[0]) if score(best)[0]>=60 else best[0]
                src='scrape'
    rows.append({**p,'domain':dom,'source':src})

json.dump(rows,open('final.json','w'),indent=1,ensure_ascii=False)
got=sum(1 for r in rows if r['domain'])
print('domains found:',got,'/',len(rows))
from collections import Counter
c=Counter((r['platform'], bool(r['domain'])) for r in rows)
pl=Counter(r['platform'] for r in rows)
for p,n in pl.most_common():
    print(f"{p:26} {c[(p,True)]:4}/{n}")
