# Security Policy

## Supported Versions

DARKSWORD is a personal GRC intelligence platform maintained by a single developer.
Only the current `main` branch is actively maintained.

| Branch | Supported |
|--------|-----------|
| `main` | ✅ Yes |
| All others | ❌ No |

---

## Reporting a Vulnerability

If you discover a security vulnerability in this repository — including hardcoded
credentials, exposed secrets, insecure dependencies, or unsafe code patterns — please
**do not open a public GitHub issue.**

Report it privately via email:

**tmon3ygrc@gmail.com**

Include:
- A description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact

I'll acknowledge receipt within 72 hours and follow up with next steps. If the report
is valid, I'll address it as quickly as possible and credit you in the fix commit if
you'd like.

---

## Scope

This repository contains:
- Pipeline orchestration code for Notion-based GRC intelligence ingestion
- No user-facing application, no authentication surface, no database
- Secrets are managed via `.env` files (gitignored) and are never committed

Pre-commit secret scanning (gitleaks) is applied to every commit on this repo.
If you see a secret that slipped through, please report it immediately.

---

## Out of Scope

- Theoretical vulnerabilities with no practical exploit path
- Issues in third-party dependencies (report those upstream)
- Social engineering
