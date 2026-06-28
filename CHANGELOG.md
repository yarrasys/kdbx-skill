# Changelog — repository

Changes to the **repository itself** — CI, issue/PR templates, marketplace plumbing, and monorepo
structure. Each **skill** has its own changelog: see `skills/<name>/CHANGELOG.md` (e.g.
[kdbx](skills/kdbx/CHANGELOG.md)). The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- Restructured as a skill-agnostic umbrella: per-skill `CHANGELOG`/`NOTICE`/`docs`/`tests` now live
  under `skills/<name>/` (+ `plugins/<name>/tests/`); repo-root governance files are generic.
- Adopted scoped release tags — each skill versions independently as `<skill>/v<version>`.
