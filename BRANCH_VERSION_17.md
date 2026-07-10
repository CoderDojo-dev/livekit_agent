# version_17 — Rollback to version_14 Clean Snapshot

## Purpose
This version restores the codebase to the exact `version_14` snapshot. Versions 15 and 16 introduced issues that blocked the pipeline, so we roll back to `origin/version_14` and will continue development from this clean base.

## What Changed
- **Base**: `origin/version_14` (commit `528a9e3`)
- **Removed**: 51 documentation files, generated reports, and ephemeral artefacts that accumulated across versions 9–16

## Removed Files (51 files, 29,550 lines)

| Category | Files |
|----------|-------|
| BRANCH_VERSION docs | `BRANCH_VERSION_10.md` through `BRANCH_VERSION_14.md` |
| System reports | `SYSTEM_CODES.md`, `PROJECT_FULL_REPORT.md`, `ALL_SYSTEM_ARCHITECTURE.md`, `CODE_DIAGNOSTIC.md`, `DIAGNOSTIC-RESOLUTION.md`, `ERROR_INVESTIGATION.md`, `SESSION_LOG_ANALYSIS.md`, `STARTUP_DIAGNOSTIC.md` |
| prompts | `prompt.md`, `start_commands.md`, `system.md` |
| System exports | `system_complete.md`, `system_complete2.md` |
| docs/architecture | Full tree |
| docs/compliance | Full tree |
| docs/patches | Full tree |
| docs/persistence | Full tree |
| docs/phase-* | Full tree |
| Other docs | `README.md` (root), `docs/RUN.md`, `docs/AI_MODEL_INVENTORY.md` |

## Code Snapshot
- **Branch point**: `origin/version_14` (HEAD `528a9e3`)
- **Working tree**: Zero code-level differences vs `origin/version_14` in `apps/`
- **Only delta**: 51 documentation deletions (no code changed)

## Next Steps
Continue development from `version_14` code, applying only verified, tested patches.
