# Temple Product Generator

Generates Peculiar People temple products on Printify from templates, one product per temple per garment. The authoritative spec is `docs/temple-catalog-generator-plan.md` (Revision 2). Work proceeds phase by phase; a phase does not start until the previous phase's gate has been confirmed by Evan.

## Status

| Phase | State |
|---|---|
| 1. Prove the API round-trip | Done, gate passed. Report: artifacts/phase1/findings.md |
| 2. Layout math | Done, gate passed 17 Aug 2026. Previews: artifacts/phase2-previews/. Decisions: docs/decisions.md |
| 3. Templates and generator | Not started |
| 4. Skill and scheduled event | Not started |
| 5. Backfill and QA | Not started |

## Setup

```
~/.pyenv/versions/3.12.8/bin/python -m venv .venv.nosync
./.venv.nosync/bin/pip install -r requirements.txt
```

Put the Printify Personal Access Token in `.env` (see the placeholder comments in that file). `.env` is gitignored and must never be committed.

## Layout

- `printify_client.py`: the Printify REST client. Shared by exploration and production code.
- `scripts/phase1.py`: Phase 1 driver. One subcommand per spec step; see `docs/phase1-runbook.md`.
- `artifacts/phase1/`: every raw API response plus `findings.md`, the Phase 1 gate report.
- `docs/`: the spec and the runbook.

Reserved at project root for later phases (do not create early): `layout.py`, `preview.py`, `generate.py`, `garments/`, `spacing_defaults.json`. Temple manifests will live in the existing `../Temples/{Name}/` folders.

The venv is named `.venv.nosync` so iCloud Drive does not sync interpreter files. If it is ever lost, recreate it from `requirements.txt`.
