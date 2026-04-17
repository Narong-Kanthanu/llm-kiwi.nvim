# Security Policy

## Supported versions

This project is under active development and follows a rolling-release
model. Security fixes land on `main` and in the latest tagged release.

| Version          | Supported          |
| ---------------- | ------------------ |
| `main`           | Yes                |
| Latest tag       | Yes                |
| Older tags       | No                 |

## Reporting a vulnerability

**Please do not file a public GitHub issue for security bugs.**

Report security issues privately via one of:

- Email: **narong@flowaccount.com** (preferred)
- GitHub private vulnerability reporting:
  <https://github.com/Narong-Kanthanu/llm-kiwi.nvim/security/advisories/new>

Please include:

- A description of the issue and its impact
- Steps to reproduce (a minimal vault or config is ideal)
- Neovim version, Python version, and OS
- Any proposed mitigation

You can expect an initial response within **7 days**. Fix timelines depend
on severity; we will coordinate a disclosure date with you.

## Scope

This plugin spawns a local Python HTTP server to render the graph and
receive click events from your browser. Please consider the following when
deploying:

- The server binds to `127.0.0.1` by default. If you configure it to bind
  to `0.0.0.0` or any non-loopback address, treat the resulting endpoint
  as untrusted — anyone on the network can trigger file-open RPCs in your
  running Neovim instance.
- The plugin reads `.md` files from the workspace paths you configure.
  Only point `workspaces` at directories you trust.
- The generated HTML loads [vis.js](https://visjs.org) from the jsDelivr
  CDN. If this is a concern, vendor the library locally and adapt
  `scripts/vault-graph.py` accordingly.

## Out of scope

- Vulnerabilities in third-party dependencies (Neovim, Python, vis.js,
  obsidian.nvim) — report those upstream.
- Attacks requiring a malicious actor to already have filesystem write
  access to your vault or plugin directory.
