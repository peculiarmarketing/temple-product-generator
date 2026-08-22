# Temple Product Generator

Generates Peculiar People temple products on Printify from templates, one product per temple per garment. The authoritative spec is `docs/temple-catalog-generator-plan.md` (Revision 2). Work proceeds phase by phase; a phase does not start until the previous phase's gate has been confirmed by Evan.

## Status

| Phase | State |
|---|---|
| 1. Prove the API round-trip | Done, gate passed. Report: artifacts/phase1/findings.md |
| 2. Layout math | Done, gate passed 17 Aug 2026. Previews: artifacts/phase2-previews/. Decisions: docs/decisions.md |
| 3. Templates and generator | Done, gate passed (Logan rehearsal; San Antonio full set generated) |
| 4. Skill and manual trigger | Done. Project skill in ../.claude/skills/; no schedule by Evan's choice |
| 5. Backfill | Closed: Evan decided no backfill. --in-place available for one-offs |

## Setup

```
uv python install 3.12.8
uv venv --python 3.12.8 --seed .venv.nosync
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

## End-of-run sequence

1. Run the sweep or a targeted generate (`generate.py --sweep` or `--temple ...`) to produce drafts.
2. (Optional) `scripts/add_date_layer.py` adds date layers to With Date drafts via the browser; skipping it means adding layers by hand as before.
3. `scripts/publish_drafts.py` publishes base drafts and verified dated drafts; economy-off drafts are held until Evan flips Economy on in the Printify UI.
