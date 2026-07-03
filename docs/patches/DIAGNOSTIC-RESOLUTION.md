# Code Diagnostic — Resolution (all 11 items)

Focus: make the platform **run with one command** and fix the dependency/import gaps. A few of these
(the duplicate `Depends`, the double `qdrant-client`) were introduced by my earlier security/infra
patches — owned and fixed here.

## What changed
| # | Diagnostic | Severity | Fix |
|---|---|---|---|
| 1 | No unified startup (20+ terminals) | HIGH | **`Makefile`** (`make dev` = install + infra + migrate + seed + run-all) + **`Procfile`** (honcho runs every service/MCP/worker/frontend in one terminal) |
| 2 | No `[project.scripts]` | HIGH | Added console scripts to the 8 services + 3 MCP servers; each FastAPI `main.py` got a `run()` entrypoint (`context-service`, `policy-service`, `business-api`, `ticketing-glpi`, …) |
| 3 | sqlalchemy imported but not declared | MEDIUM | Added `sqlalchemy>=2.0,<2.1` to context / policy / execution / business-api |
| 4 | httpx imported but not declared | MEDIUM | Added `httpx==0.28.1` to notification-client + knowledge-service |
| 5 | Duplicate `from fastapi import Depends` (my PS1) | LOW | Merged into one import in all 6 service mains |
| 6 | Two out-of-sync `.env.example` | MEDIUM | `deploy/secrets/.env.example` is now a **pointer** to the single root template (no deprecated names) |
| 7 | Undocumented install order | HIGH | Encoded in `make install` (shared packages first, in order) + written in `docs/RUN.md` |
| 8 | No compose app definitions | MEDIUM | **`infra/docker-compose/docker-compose.apps.yml`** — all 8 services + 3 MCP + worker (`make up`) |
| 9 | LiveKit self-hosted wasted on Cloud | LOW | `livekit-server` moved behind an **opt-in compose profile** `self-hosted-livekit` (`make infra-livekit`) |
| 10 | Mandatory qdrant-client dep | LOW | Moved to an **optional extra** `[project.optional-dependencies] qdrant`; de-duplicated; retriever import-guards it (lexical fallback) |
| 11 | No health/smoke script | MEDIUM | **`scripts/health_check.py`** (`make health`) probes every `/health`; **`scripts/run_tests.py`** (`make test`) runs the offline suite |

## How you run it now
```bash
cp .env.example .env          # fill the ⚠ values (LiveKit + provider keys)
make dev                      # install (correct order) → infra → migrate → seed → honcho start (everything)
make frontends                # first time only: npm install the two web apps
make health                   # probe all services
```
Container path instead of honcho: `make up` (builds + runs everything), `make down` to stop.
On LiveKit Cloud? Do nothing — the self-hosted server won't start. Local LiveKit: `make infra-livekit`.

## Verification (offline)
Touched suites all green — context 4 · policy 10 · execution 5 · notification 6 · knowledge 3 ·
business-api 7; every service `main.py` imports with its new `run()`. All `pyproject.toml` parse as
valid TOML; both docker-compose files + the gateway compose parse as valid YAML; `Makefile` parses;
the two scripts byte-compile; `livekit-server` carries the `self-hosted-livekit` profile.

## Note on the two remaining "structural" observations
- **#7 install order** can't be fully removed (it's inherent to a monorepo of editable packages), but
  `make install` means you never type it by hand.
- **#9 LiveKit** is now opt-in; if you're on Cloud, the container simply never starts.
