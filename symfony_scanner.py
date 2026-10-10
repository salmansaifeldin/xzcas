#!/usr/bin/env python3
"""
Symfony Vulnerability Scanner
=============================
Detection-only scanner for the following Symfony-related issues:

  1. Secret Fragments / /_fragment RCE pattern
     (misuse of FragmentListener + leaked/weak APP_SECRET; related historic CVEs:
      CVE-2012-6432, CVE-2014-5245, CVE-2015-4050 — no single CVE for the
      Ambionics "Secret Fragments" technique).
  2. CachingHttpClient RCE          -> CVE-2020-15094
  3. Symfony 1 Deserialization      -> CVE-2024-28861
  4. Runtime (argv / env hijack)    -> CVE-2024-50340
  5. Process hijacking on Windows   -> CVE-2024-51736

NOTE: This scanner performs *non-destructive detection only*. It fingerprints
the stack / exposed surface (headers, debug tokens, profiler, _fragment
behavior, Symfony 1 markers, composer.lock exposure, exposed .env, etc.)
and reports a per-CVE verdict with a confidence level. It does NOT fire
working exploit payloads at live targets.

Usage:
    python3 symfony_scanner.py -l domains.txt
    python3 symfony_scanner.py -l domains.txt -o results.json --threads 20

Authorized use only (bug-bounty scope / signed engagement / own assets).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import sys
import urllib.parse
import urllib3
from dataclasses import dataclass, field, asdict
from typing import Optional

try:
    import requests
except ImportError:
    print("[-] Missing dependency: pip install requests", file=sys.stderr)
    sys.exit(1)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UA = "SymfonyVulnScanner/1.0 (+bugbounty-detection; contact=researcher)"
DEFAULT_TIMEOUT = 10

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CveResult:
    cve: str
    name: str
    vulnerable: bool = False
    confidence: str = "none"      # none | low | medium | high
    evidence: list = field(default_factory=list)


@dataclass
class TargetResult:
    target: str
    reachable: bool = False
    is_symfony: bool = False
    symfony_version: Optional[str] = None
    is_symfony1: bool = False
    findings: list = field(default_factory=list)

    @property
    def any_vulnerable(self) -> bool:
        return any(f.vulnerable for f in self.findings)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def normalize(url: str) -> str:
    url = url.strip()
    if not url:
        return url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def http_get(session, url, **kw):
    kw.setdefault("timeout", DEFAULT_TIMEOUT)
    kw.setdefault("verify", False)
    kw.setdefault("allow_redirects", True)
    try:
        return session.get(url, **kw)
    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------

SYMFONY_HEADER_HINTS = ("x-debug-token", "x-debug-token-link", "x-symfony-cache")
SYMFONY_COOKIE_HINTS = ("symfony=", "sf_redirect", "PHPSESSID")

VERSION_RE = re.compile(r"Symfony\s*/?\s*(\d+(?:\.\d+){1,2})", re.IGNORECASE)


def fingerprint(session, base, result: TargetResult):
    r = http_get(session, base + "/")
    if r is None:
        return
    result.reachable = True

    headers = {k.lower(): v for k, v in r.headers.items()}
    for h in SYMFONY_HEADER_HINTS:
        if h in headers:
            result.is_symfony = True
            break

    # X-Powered-By
    xpb = headers.get("x-powered-by", "")
    if "symfony" in xpb.lower() or "php" in xpb.lower():
        if "symfony" in xpb.lower():
            result.is_symfony = True
        m = VERSION_RE.search(xpb)
        if m:
            result.symfony_version = m.group(1)

    # Error page / debug page sniff
    for probe in ("/_profiler", "/app_dev.php", "/_wdt", "/does-not-exist-" + "sfprobe"):
        rp = http_get(session, base + probe)
        if rp is None:
            continue
        body = (rp.text or "")[:4000]
        if "Symfony" in body or "symfony" in body:
            result.is_symfony = True
            m = VERSION_RE.search(body)
            if m and not result.symfony_version:
                result.symfony_version = m.group(1)
        if re.search(r"symfony/symfony\s+1\.", body, re.I) or "sfContext" in body:
            result.is_symfony1 = True

    # composer.lock / composer.json exposure (common misconfig)
    for probe in ("/composer.lock", "/composer.json"):
        rp = http_get(session, base + probe)
        if rp is not None and rp.status_code == 200 and "symfony/" in (rp.text or "").lower():
            result.is_symfony = True
            m = re.search(r'"symfony/symfony"\s*:\s*"([^"]+)"', rp.text or "")
            if m and not result.symfony_version:
                result.symfony_version = m.group(1).lstrip("v^~=")
            m2 = re.search(r'"symfony/http-kernel".{0,200}?"version"\s*:\s*"([^"]+)"',
                           rp.text or "", re.S)
            if m2 and not result.symfony_version:
                result.symfony_version = m2.group(1).lstrip("v")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_fragment(session, base, result: TargetResult) -> CveResult:
    """
    Detect exposure of /_fragment (FragmentListener) endpoint. We do NOT send
    a signed exploit payload. We just check whether the endpoint exists and
    rejects unsigned requests the way vulnerable installs typically do.
    Also flag debug mode / .env exposure that would leak APP_SECRET.
    """
    c = CveResult(
        cve="FRAGMENT-RCE",
        name="/_fragment + APP_SECRET (Secret Fragments pattern)",
    )

    # 1. /_fragment reachability
    r = http_get(session, base + "/_fragment")
    if r is not None and r.status_code in (400, 403, 500):
        body = (r.text or "").lower()
        if ("hash" in body or "signature" in body or "_hash" in body
                or "fragment" in body or "accessdenied" in body):
            c.vulnerable = True
            c.confidence = "low"
            c.evidence.append(f"/_fragment responds {r.status_code} with signature-check wording")

    # 2. .env exposure (leaks APP_SECRET -> turns low -> high)
    for probe in ("/.env", "/.env.local", "/.env.prod", "/.env.dev"):
        rp = http_get(session, base + probe)
        if rp is not None and rp.status_code == 200 and "APP_SECRET" in (rp.text or ""):
            c.vulnerable = True
            c.confidence = "high"
            c.evidence.append(f"{probe} exposes APP_SECRET")
            break

    # 3. Debug mode / profiler exposure
    for probe in ("/_profiler", "/app_dev.php/_profiler", "/_profiler/empty/search/results"):
        rp = http_get(session, base + probe)
        if rp is not None and rp.status_code == 200 and "profiler" in (rp.text or "").lower():
            c.vulnerable = True
            if c.confidence in ("none", "low"):
                c.confidence = "medium"
            c.evidence.append(f"Symfony profiler exposed at {probe}")
            break

    return c


def check_caching_http_client(session, base, result: TargetResult) -> CveResult:
    """
    CVE-2020-15094: affects symfony/http-client < 4.4.13 / < 5.1.5 when the
    CachingHttpClient is used with attacker-controlled responses. We can only
    fingerprint by version from composer.lock when exposed.
    """
    c = CveResult(cve="CVE-2020-15094", name="CachingHttpClient RCE")

    rp = http_get(session, base + "/composer.lock")
    if rp is not None and rp.status_code == 200:
        text = rp.text or ""
        m = re.search(r'"symfony/http-client".{0,300}?"version"\s*:\s*"v?([\d.]+)"', text, re.S)
        if m:
            ver = m.group(1)
            if _version_lt(ver, "4.4.13") or (
                _version_ge(ver, "5.0.0") and _version_lt(ver, "5.1.5")
            ):
                c.vulnerable = True
                c.confidence = "medium"
                c.evidence.append(f"symfony/http-client version {ver} is in the vulnerable range")

    return c


def check_symfony1_deser(session, base, result: TargetResult) -> CveResult:
    """
    CVE-2024-28861: deserialization in Symfony 1 gadget chain.
    Detection: Symfony 1 markers (sf_* cookies, symfony/symfony1 in exposed
    composer, legacy error pages).
    """
    c = CveResult(cve="CVE-2024-28861", name="Symfony 1 Deserialization")

    if result.is_symfony1:
        c.vulnerable = True
        c.confidence = "medium"
        c.evidence.append("Symfony 1 markers detected on target")
        return c

    # Extra probes
    rp = http_get(session, base + "/composer.lock")
    if rp is not None and rp.status_code == 200:
        if re.search(r'"friendsofsymfony1/symfony1"|"symfony/symfony".{0,80}"1\.', rp.text or ""):
            c.vulnerable = True
            c.confidence = "medium"
            c.evidence.append("composer.lock pins Symfony 1.x")
            result.is_symfony1 = True

    # sfContext / sf_guard footprint
    for probe in ("/frontend_dev.php", "/backend_dev.php", "/sfGuardAuth/signin"):
        rp = http_get(session, base + probe)
        if rp is not None and rp.status_code in (200, 302, 500):
            body = (rp.text or "").lower()
            if "sfcontext" in body or "symfony 1" in body or "sfguard" in body:
                c.vulnerable = True
                c.confidence = "medium"
                c.evidence.append(f"Symfony 1 artifact at {probe}")
                result.is_symfony1 = True
                break

    return c


def check_runtime_argv(session, base, result: TargetResult) -> CveResult:
    """
    CVE-2024-50340: symfony/runtime <= 7.1.6 (and corresponding 5.x/6.x lines)
    reads argv / environment unsafely under PHP-FPM when register_argc_argv
    is enabled, letting a crafted query string poison $_SERVER['argv'].
    Detection: version from composer.lock + check that PHP exposes argc/argv
    via query string.
    """
    c = CveResult(cve="CVE-2024-50340", name="Runtime argv/env hijack")

    bad_versions_hit = False
    rp = http_get(session, base + "/composer.lock")
    if rp is not None and rp.status_code == 200:
        m = re.search(r'"symfony/runtime".{0,300}?"version"\s*:\s*"v?([\d.]+)"',
                      rp.text or "", re.S)
        if m:
            ver = m.group(1)
            # Fixed in 5.4.46 / 6.4.14 / 7.1.7
            if (_version_lt(ver, "5.4.46")
                or (_version_ge(ver, "6.0.0") and _version_lt(ver, "6.4.14"))
                or (_version_ge(ver, "7.0.0") and _version_lt(ver, "7.1.7"))):
                bad_versions_hit = True
                c.evidence.append(f"symfony/runtime {ver} is in the vulnerable range")

    # register_argc_argv probe: on misconfigured PHP-FPM, a crafted query
    # string becomes $_SERVER['argv']. We just probe for a reflection in a
    # Symfony error page without expecting code execution.
    probe = "?" + urllib.parse.quote("--sfprobe-marker-xzcas")
    rp = http_get(session, base + "/" + probe)
    if rp is not None and "sfprobe-marker-xzcas" in (rp.text or ""):
        c.evidence.append("query string reflected into process args/env context")
        bad_versions_hit = True

    if bad_versions_hit:
        c.vulnerable = True
        c.confidence = "medium" if len(c.evidence) >= 2 else "low"

    return c


def check_process_windows(session, base, result: TargetResult) -> CveResult:
    """
    CVE-2024-51736: symfony/process on Windows — PATH-based process hijack.
    Detection: Windows server + vulnerable symfony/process version.
    """
    c = CveResult(cve="CVE-2024-51736", name="Process hijack on Windows")

    is_windows = False
    r = http_get(session, base + "/")
    if r is not None:
        srv = r.headers.get("Server", "") + " " + r.headers.get("X-Powered-By", "")
        if re.search(r"win(dows|64|32)|iis|microsoft", srv, re.I):
            is_windows = True
            c.evidence.append(f"Windows server banner: {srv.strip()}")

    bad_version = False
    rp = http_get(session, base + "/composer.lock")
    if rp is not None and rp.status_code == 200:
        m = re.search(r'"symfony/process".{0,300}?"version"\s*:\s*"v?([\d.]+)"',
                      rp.text or "", re.S)
        if m:
            ver = m.group(1)
            # Fixed in 5.4.46 / 6.4.14 / 7.1.7
            if (_version_lt(ver, "5.4.46")
                or (_version_ge(ver, "6.0.0") and _version_lt(ver, "6.4.14"))
                or (_version_ge(ver, "7.0.0") and _version_lt(ver, "7.1.7"))):
                bad_version = True
                c.evidence.append(f"symfony/process {ver} is in the vulnerable range")

    if is_windows and bad_version:
        c.vulnerable = True
        c.confidence = "high"
    elif bad_version:
        c.vulnerable = True
        c.confidence = "low"
        c.evidence.append("OS not confirmed Windows — may be false positive")

    return c


# ---------------------------------------------------------------------------
# Version compare
# ---------------------------------------------------------------------------

def _vt(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3] + ["0"] * 3)[:3]


def _version_lt(a, b): return _vt(a) < _vt(b)
def _version_ge(a, b): return _vt(a) >= _vt(b)


# ---------------------------------------------------------------------------
# Per-target orchestration
# ---------------------------------------------------------------------------

def scan_target(raw_target: str) -> TargetResult:
    base = normalize(raw_target)
    result = TargetResult(target=base)
    if not base:
        return result

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "*/*"})

    fingerprint(session, base, result)
    if not result.reachable:
        return result

    for check in (
        check_fragment,
        check_caching_http_client,
        check_symfony1_deser,
        check_runtime_argv,
        check_process_windows,
    ):
        try:
            result.findings.append(check(session, base, result))
        except Exception as e:
            result.findings.append(CveResult(
                cve=check.__name__, name=check.__name__,
                vulnerable=False, confidence="none",
                evidence=[f"error: {e!r}"],
            ))

    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

GREEN = "\033[32m"; RED = "\033[31m"; YEL = "\033[33m"
DIM = "\033[2m"; BOLD = "\033[1m"; RST = "\033[0m"


def print_result(r: TargetResult):
    if not r.reachable:
        print(f"{DIM}[unreachable] {r.target}{RST}")
        return

    tag = f"{BOLD}{r.target}{RST}"
    sym = ""
    if r.is_symfony:
        sym = f" (Symfony{' ' + r.symfony_version if r.symfony_version else ''}"
        if r.is_symfony1:
            sym += ", v1"
        sym += ")"

    if r.any_vulnerable:
        print(f"{RED}[VULNERABLE]{RST} {tag}{sym}  -> True")
        for f in r.findings:
            if f.vulnerable:
                print(f"    {YEL}- {f.cve}{RST}  [{f.confidence}]  {f.name}")
                for e in f.evidence:
                    print(f"        · {e}")
    else:
        print(f"{GREEN}[clean]{RST}      {tag}{sym}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Symfony vulnerability scanner (detection-only)")
    ap.add_argument("-l", "--list", required=True, help="file with one domain per line")
    ap.add_argument("-o", "--output", help="write JSON results to this file")
    ap.add_argument("-t", "--threads", type=int, default=10, help="concurrent targets")
    global DEFAULT_TIMEOUT  # noqa: PLW0603
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="per-request timeout")
    ap.add_argument("--only-vuln", action="store_true", help="print only vulnerable targets")
    args = ap.parse_args()
    DEFAULT_TIMEOUT = args.timeout

    try:
        with open(args.list) as f:
            targets = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except OSError as e:
        print(f"[-] cannot read {args.list}: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"[*] Loaded {len(targets)} targets. Threads={args.threads} Timeout={DEFAULT_TIMEOUT}s")
    print(f"[*] UA: {UA}")
    print()

    results = []
    with cf.ThreadPoolExecutor(max_workers=args.threads) as ex:
        for r in ex.map(scan_target, targets):
            results.append(r)
            if args.only_vuln and not r.any_vulnerable:
                continue
            print_result(r)

    # Summary
    vuln = [r for r in results if r.any_vulnerable]
    print()
    print(f"{BOLD}Summary:{RST} {len(vuln)}/{len(results)} vulnerable")
    for r in vuln:
        cves = ",".join(f.cve for f in r.findings if f.vulnerable)
        print(f"  {r.target}  -> True  [{cves}]")

    if args.output:
        with open(args.output, "w") as f:
            json.dump([_to_dict(r) for r in results], f, indent=2)
        print(f"[*] JSON written to {args.output}")


def _to_dict(r: TargetResult) -> dict:
    d = asdict(r)
    d["any_vulnerable"] = r.any_vulnerable
    return d


if __name__ == "__main__":
    main()
