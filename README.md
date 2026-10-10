# Symfony Vulnerability Scanner

Detection-only scanner for a handful of Symfony-related issues:

| Issue                                               | CVE              |
|-----------------------------------------------------|------------------|
| `/_fragment` + weak/leaked `APP_SECRET` (Secret Fragments pattern) | — (misuse; related historic: CVE-2012-6432, CVE-2014-5245, CVE-2015-4050) |
| CachingHttpClient RCE                               | CVE-2020-15094   |
| Symfony 1 Deserialization                           | CVE-2024-28861   |
| Runtime (argv / environment manipulation)           | CVE-2024-50340   |
| Process hijacking on Windows                        | CVE-2024-51736   |

## Install

```bash
pip install requests
```

## Usage

```bash
python3 symfony_scanner.py -l domains.txt
python3 symfony_scanner.py -l domains.txt -o results.json --threads 20 --only-vuln
```

`domains.txt` is one target per line (`example.com`, `https://host.tld`, etc.).

The script prints each target and, when vulnerable, prints the domain with
`-> True` plus which CVE(s) matched and the evidence that led to the
verdict.

## What the scanner does and does not do

- Fingerprints the stack from headers, cookies, debug/profiler surface,
  `composer.lock` / `composer.json` exposure, and `.env` exposure.
- Flags vulnerable **versions** when `composer.lock` is readable.
- Flags exposed `/_fragment`, exposed profiler, and `APP_SECRET` leaks.
- **Does not** send working exploit payloads, deserialization gadgets,
  signed fragment URIs, or anything that would alter server state.

The verdict `True` means "detection matched". Confirm with a manual,
scoped PoC before reporting.

## Authorization

Use only against targets you are explicitly authorized to test
(bug-bounty scope, signed engagement, or your own assets).
