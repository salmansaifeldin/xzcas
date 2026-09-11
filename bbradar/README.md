# bbradar.io scrape — targets + domains

Scraped all 58 listing pages of https://bbradar.io ( `?page=1` .. `?page=58` ).

- **Programs (targets): 1439**
- **With a domain resolved: 1137** (1035 unique domains)

## Files

| File | Contents |
|---|---|
| `bbradar_targets.csv` | full table: name, platform, domain, source, bbradar URL, program URL |
| `bbradar_targets.txt` | plain `name -> domain` list |
| `bbradar_domains.txt` | unique domains only (one per line, ready for recon tooling) |
| `bbradar_programs.json` | raw structured data |

## How domains were obtained

| source | count | meaning |
|---|---|---|
| `hackerone` | 206 | official `website` field from the HackerOne GraphQL API |
| `scrape` | 607 | extracted from the program page on its bug-bounty platform |
| `inferred` | 324 | derived from the program name, then verified by DNS + live page content |

`inferred` rows are best-effort: the domain resolves and its homepage mentions the name, but a few short/generic
names can still map to the wrong company. Verify those before using them as scope.

## Coverage by platform

| Platform | With domain | Total |
|---|---|---|
| BugCrowd | 187 | 279 |
| HackerOne | 218 | 223 |
| HackenProof | 157 | 191 |
| Immunefi | 179 | 181 |
| Intigriti | 86 | 88 |
| Standoff365 | 44 | 88 |
| BI.ZONE | 12 | 69 |
| YesWeHack | 54 | 57 |
| Cantina | 48 | 50 |
| BugRap | 29 | 50 |
| Sherlock | 31 | 35 |
| Inspectiv | 30 | 34 |
| Remedy | 25 | 31 |
| IssueHunt | 8 | 15 |
| Compass Security | 7 | 12 |
| Bug Bounty Switzerland | 2 | 12 |
| GObugfree | 8 | 8 |
| Bugbase | 5 | 5 |
| AuditOne | 2 | 4 |
| PatchDay | 1 | 3 |
| CertiK | 2 | 2 |
| Huntr | 1 | 1 |
| HackZar | 1 | 1 |

## Not resolvable

Some platforms keep program scope behind a login, and bbradar itself puts target identities behind Pro,
so these programs have no public domain: BI.ZONE, Standoff365, BugRap, IssueHunt, Bug Bounty Switzerland,
Compass Security (hosted on Hacking-Lab), and part of Bugcrowd's managed engagements.
