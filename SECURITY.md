# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main`  | ✅ Yes     |

Only the current `main` branch receives security fixes.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report security issues privately by emailing **coding.projects.1642@proton.me**.

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested mitigations (optional)

You will receive an acknowledgment within 72 hours. We aim to release a fix within 14 days of a confirmed report, depending on severity and complexity.

## Scope

TeamExecutor orchestrates coordinator/worker/verifier multi-agent execution. The primary security surface is:

- **Arbitrary command execution** via Claude Code worker subprocess
- **Prompt injection** — untrusted stage content reaching the coordinator or verifier
- **API token exposure** via config files or logs (`ANTHROPIC_API_KEY`)
- **goal_text rewriting** — anything that modifies task content before it reaches workers (D1 invariant violation)
- **Log injection** via untrusted stage output written to structured logs

## Out of Scope

- Vulnerabilities in upstream AI providers or Claude Code
- Issues requiring physical access to the host machine
- Denial-of-service via normal task load (rate limiting is a configuration concern)
