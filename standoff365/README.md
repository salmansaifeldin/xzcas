# Standoff 365 Bug Bounty — programs + scope domains

Scraped from https://bugbounty.standoff365.com/en-US/programs

- **Programs: 88** (the full public catalogue)
- **With scope domains: 69**
- **620 scope entries**, **169 unique root domains**

Unlike the bbradar pass, this one gets the **real in-scope assets**, not just one
company domain per program — wildcards (`*.vk.cc`) and individual hosts included.

## Files

| File | Contents |
|---|---|
| `standoff365_programs.csv` | one row per program: name, vendor, primary domain, scope count, status |
| `standoff365_scope.csv` | one row per scope entry: program, vendor, scope entry, root domain |
| `standoff365_domains.txt` | every unique scope entry, one per line |
| `standoff365_roots.txt` | unique root domains only |
| `standoff365_targets.txt` | readable program -> domains tree |
| `standoff365_programs.json` | raw structured data |

## Method

Standoff 365 exposes an unauthenticated API: `GET https://api.standoff365.com/api/bug-bounty/program?page=N`
(5 per page, 18 pages). It returns the full program object including the `description`
markdown, which is where the scope actually lives — there is no structured scope field
(the `scopes` array in the site payload is empty for every program).

Domains were parsed out of that markdown, plus the rendered program pages in both the
`en-US` and `ru-RU` locales, since some programs only have text in one of them.
Regex alternations used by the site (`vk.(com|ru)`) are expanded into separate entries.

## Programs without domains (19)

Mostly Positive Technologies on-prem products (PT NGFW, MaxPatrol SIEM/VM/EDR, PT Sandbox,
PT ISIM ...) where the target is a downloadable product rather than a web asset, plus a few
with a physical scope (Innostage's Wi-Fi network) or an empty public description.
