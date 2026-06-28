# Security Policy

This repository hosts multiple agent skills; **each skill ships its own threat model and security
notes** under `skills/<name>/references/security.md` (e.g.
[`skills/kdbx/references/security.md`](skills/kdbx/references/security.md)). Read the relevant skill's
docs before relying on it.

General posture:

- **No warranty.** Everything here is provided "as is" under the MIT License — audit a skill before
  relying on it for anything that matters.
- Skills that manage secrets keep them outside any repo and never commit them; see the skill's docs
  for its specific handling guarantees.

## Reporting a vulnerability

Please report suspected vulnerabilities privately rather than opening a public issue — either through
GitHub's [private vulnerability reporting](https://github.com/yarrasys/extensions/security/advisories/new)
or by email to **hello@yarrasys.com**. Include a description, repro steps, and impact. You'll get an
acknowledgement and a fix timeline.
