#!/usr/bin/env python3
"""Check HTTPS / TLS certificates for a fixed set of domains."""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

DEFAULT_DOMAINS = [
    "shaneqi.dev",
    "www.shaneqi.dev",
    "shaneqi.com",
    "www.shaneqi.com",
    "ruzhang.dev",
    "www.ruzhang.dev",
    "eastwatch.app",
    "www.eastwatch.app",
    "eastwatchapp.com",
    "www.eastwatchapp.com",
    "qis.family",
    "www.qis.family",
]

WARN_DAYS = 30
CRITICAL_DAYS = 14
DEFAULT_TIMEOUT = 10.0
DEFAULT_PORT = 443


def _parse_cert_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _flatten_name(entries: Any) -> dict[str, str]:
    parts: dict[str, str] = {}
    for rdn in entries or ():
        parts.update(dict(rdn))
    return parts


def _sans(cert: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for kind, value in cert.get("subjectAltName") or ():
        if kind == "DNS":
            names.append(value)
    return names


def _apply_cert_fields(result: dict[str, Any], cert: dict[str, Any], now: datetime) -> None:
    result["subject"] = _flatten_name(cert.get("subject"))
    result["issuer"] = _flatten_name(cert.get("issuer"))
    result["sans"] = _sans(cert)
    not_before = _parse_cert_datetime(cert.get("notBefore"))
    not_after = _parse_cert_datetime(cert.get("notAfter"))
    result["not_before"] = not_before.isoformat() if not_before else None
    result["not_after"] = not_after.isoformat() if not_after else None
    if not_after:
        days = (not_after - now).total_seconds() / 86400.0
        result["days_remaining"] = round(days, 1)


def check_domain(
    host: str,
    *,
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_TIMEOUT,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "host": host,
        "port": port,
        "ok": False,
        "status": "error",
        "error": None,
        "verified": False,
        "subject": {},
        "issuer": {},
        "sans": [],
        "not_before": None,
        "not_after": None,
        "days_remaining": None,
        "tls_version": None,
        "cipher": None,
    }

    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                result["verified"] = True
                result["tls_version"] = ssock.version()
                cipher = ssock.cipher()
                if cipher:
                    result["cipher"] = cipher[0]
                _apply_cert_fields(result, cert, now)
                days = result.get("days_remaining")
                if days is None:
                    result["status"] = "ok"
                    result["ok"] = True
                    result["error"] = "could not parse notAfter"
                elif days < 0:
                    result["status"] = "expired"
                    result["error"] = f"certificate expired {-days:.1f} days ago"
                elif days <= CRITICAL_DAYS:
                    result["status"] = "critical"
                    result["ok"] = True
                elif days <= WARN_DAYS:
                    result["status"] = "warn"
                    result["ok"] = True
                else:
                    result["status"] = "ok"
                    result["ok"] = True
    except ssl.SSLCertVerificationError as exc:
        result["error"] = f"verification failed: {exc.reason or exc}"
        result["status"] = "untrusted"
        # Still try to pull peer cert without verification for diagnostics
        try:
            insecure = ssl._create_unverified_context()
            with socket.create_connection((host, port), timeout=timeout) as sock:
                with insecure.wrap_socket(sock, server_hostname=host) as ssock:
                    _apply_cert_fields(result, ssock.getpeercert(), now)
        except Exception:
            pass
    except (socket.timeout, TimeoutError):
        result["error"] = f"timed out after {timeout}s"
        result["status"] = "unreachable"
    except socket.gaierror as exc:
        result["error"] = f"DNS error: {exc.strerror or exc}"
        result["status"] = "unreachable"
    except OSError as exc:
        result["error"] = f"connection error: {exc.strerror or exc}"
        result["status"] = "unreachable"
    except Exception as exc:  # noqa: BLE001 — surface unexpected failures per host
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["status"] = "error"

    return result


def check_domains(
    domains: list[str],
    *,
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_TIMEOUT,
    workers: int = 8,
) -> list[dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(domains) or 1))) as pool:
        futures = {
            pool.submit(check_domain, host, port=port, timeout=timeout): host for host in domains
        }
        for future in as_completed(futures):
            host = futures[future]
            try:
                results[host] = future.result()
            except Exception as exc:  # noqa: BLE001
                results[host] = {
                    "host": host,
                    "port": port,
                    "ok": False,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "verified": False,
                    "subject": {},
                    "issuer": {},
                    "sans": [],
                    "not_before": None,
                    "not_after": None,
                    "days_remaining": None,
                    "tls_version": None,
                    "cipher": None,
                }
    return [results[host] for host in domains]


def _issuer_label(result: dict[str, Any]) -> str:
    issuer = result.get("issuer") or {}
    org = issuer.get("organizationName")
    cn = issuer.get("commonName")
    if org and cn:
        return f"{org} ({cn})"
    return org or cn or "—"


def format_text(results: list[dict[str, Any]]) -> str:
    status_order = {
        "expired": 0,
        "critical": 1,
        "untrusted": 2,
        "warn": 3,
        "unreachable": 4,
        "error": 5,
        "ok": 6,
    }
    lines: list[str] = []
    lines.append(
        f"{'HOST':<28} {'STATUS':<12} {'DAYS':>7}  {'EXPIRES (UTC)':<28} ISSUER"
    )
    lines.append("-" * 100)
    for r in results:
        days = r.get("days_remaining")
        days_s = f"{days:.0f}" if isinstance(days, (int, float)) else "—"
        expires = r.get("not_after") or "—"
        if isinstance(expires, str):
            expires = expires.replace("+00:00", "Z")
        err = f"  ({r['error']})" if r.get("error") and r["status"] != "ok" else ""
        lines.append(
            f"{r['host']:<28} {r['status']:<12} {days_s:>7}  {expires:<28} {_issuer_label(r)}{err}"
        )

    problem_count = sum(1 for r in results if r["status"] != "ok")
    ok_count = len(results) - problem_count
    lines.append("")
    lines.append(f"Summary: {ok_count}/{len(results)} ok, {problem_count} need attention")
    if problem_count:
        worst = sorted(results, key=lambda r: status_order.get(r["status"], 99))
        lines.append("Attention:")
        for r in worst:
            if r["status"] == "ok":
                continue
            detail = r.get("error") or f"expires in {r.get('days_remaining')} days"
            lines.append(f"  - {r['host']}: {r['status']} — {detail}")
    return "\n".join(lines)


def exit_code(results: list[dict[str, Any]]) -> int:
    statuses = {r["status"] for r in results}
    if statuses & {"expired", "critical", "untrusted", "unreachable", "error"}:
        return 2
    if "warn" in statuses:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "domains",
        nargs="*",
        help="Optional hostnames to check (default: built-in domain list)",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a table",
    )
    args = parser.parse_args(argv)

    domains = args.domains or list(DEFAULT_DOMAINS)
    results = check_domains(
        domains, port=args.port, timeout=args.timeout, workers=args.workers
    )

    if args.json:
        print(
            json.dumps(
                {
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "results": results,
                },
                indent=2,
            )
        )
    else:
        print(format_text(results))

    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
