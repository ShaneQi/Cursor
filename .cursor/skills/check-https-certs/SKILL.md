---
name: check-https-certs
description: >-
  Checks HTTPS/TLS certificates for Shane Qi domains (shaneqi.dev, shaneqi.com,
  ruzhang.dev, eastwatch.app, eastwatchapp.com, qis.family, and their www hosts).
  Use when asked to check SSL/TLS/HTTPS certificates, cert expiry, renewal status,
  or certificate health for these domains.
---

# Check HTTPS Certificates

When the user asks to check SSL/TLS/HTTPS certificates (expiry, validity, or
health) for the personal domains below, run the helper immediately and report
the results. Do not invent cert status from memory.

## Domains (default set)

- `shaneqi.dev` / `www.shaneqi.dev`
- `shaneqi.com` / `www.shaneqi.com`
- `ruzhang.dev` / `www.ruzhang.dev`
- `eastwatch.app` / `www.eastwatch.app`
- `eastwatchapp.com` / `www.eastwatchapp.com`
- `qis.family` / `www.qis.family`

## Steps

1. Run the checker (defaults to the full domain list):

```bash
python3 .cursor/skills/check-https-certs/scripts/check-https-certs.py
```

Optional: check a subset, or emit JSON:

```bash
python3 .cursor/skills/check-https-certs/scripts/check-https-certs.py shaneqi.dev www.shaneqi.dev
python3 .cursor/skills/check-https-certs/scripts/check-https-certs.py --json
```

2. Summarize for the user:
   - Overall pass/fail (how many hosts are healthy vs need attention)
   - Any `expired`, `critical` (≤14 days), `warn` (≤30 days), `untrusted`, or `unreachable` hosts
   - For problem hosts: hostname, status, days remaining / error, issuer when available
   - Keep healthy hosts brief (or omit details unless asked)

3. Exit codes from the script (use when deciding severity):
   - `0` — all hosts ok (>30 days remaining, verified)
   - `1` — at least one `warn` (≤30 days), none critical/expired/unreachable
   - `2` — at least one `expired`, `critical`, `untrusted`, `unreachable`, or `error`

## Notes

- Requires outbound HTTPS (TCP 443) and working DNS for each host.
- The script verifies the chain with the system trust store and reports TLS version.
- Prefer the helper over ad-hoc `openssl s_client` unless debugging a single host further.
- Do not claim renewal/fix actions completed unless the user asked you to renew and you actually did.
