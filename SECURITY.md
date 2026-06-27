# Security Policy

> ⚠️ This project is in the design phase and not yet implemented. Do not use it
> to store real secrets until its test suite is green.

## Threat model & design posture

The full threat model — key-file-only unlock, secret-handling invariants
(the agent never authors or observes a value; nothing on argv/stdout), the
0600/ACL permission model, the soft-delete-is-recoverable property, and the
`run` env-injection trust boundary — is documented in the design spec
(`docs/superpowers/specs/2026-06-27-kdbx-skill-design.md`, §8/§12) and will move
to `references/security.md` on implementation.

Key points a user must understand:

- **The key file is the sole secret.** Anyone who can read the key file *and*
  the vault can open it. Losing the key file makes the vault unrecoverable.
- **Secrets live outside any repo**, under the user config dir — never committed.
- **No warranty.** Provided "as is" under the MIT License. Audit before relying
  on it for anything that matters.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to the maintainer rather than
opening a public issue: **nabsha.dev@gmail.com**. Include a description, repro
steps, and impact. You'll get an acknowledgement and a fix timeline.
