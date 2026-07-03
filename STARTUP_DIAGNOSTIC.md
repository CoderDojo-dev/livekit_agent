# Startup Diagnostic Report

**Generated:** 2026-07-02  
**Scope:** All errors encountered while attempting to run the Telecom AI Voice Agent Platform from a PowerShell terminal with a Python 3.12 `.venv`.

---

## ERROR 1 — PowerShell `&&` chaining (bash syntax on Windows)

**Count:** 9 occurrences across multiple attempts

**Error:**
```
The token '&&' is not a valid statement separator in this version.
```

**Exact command that failed:**
```powershell
cd apps/supervisor-dashboard && npm run dev   # :5174
cd apps/client-widget && npm run dev          # :5173
```

**Root cause:**  
`&&` is Bash syntax. PowerShell (the user's shell) uses `;` for sequential commands. The `#` comment syntax is also bash-only — PowerShell comments use `<# ... #>` block syntax.

**Affected instructions:**  
All run commands previously provided to the user contained `&&` and shell-style comments.

**Correct PowerShell equivalents:**
```powershell
cd apps\supervisor-dashboard; npm run dev
cd apps\client-widget; npm run dev
```

---

## ERROR 2 — Relative-path `.venv` activation from wrong directory

**Count:** 4 occurrences

**Error:**
```
.\.venv\Scripts\Activate.ps1 : The term '.\.venv\Scripts\Activate.ps1' is not recognized
as the name of a cmdlet, function, script file, or operable program.
```

**File/Line:** User's terminal — command invoked from subdirectory

**Root cause:**  
The user was inside a subdirectory (e.g. `apps\business-api`) when typing `.\.venv\Scripts\Activate.ps1`. The `.venv` directory sits at the **project root**, so the relative path is only valid from `C:\Users\Chouqib Saad\Desktop\telecom-ai-agent-platform`.

**Correct activation command (must be run from project root):**
```powershell
cd C:\Users\Chouqib Saad\Desktop\telecom-ai-agent-platform
.\.venv\Scripts\Activate.ps1
```

---

## ERROR 3 — `cd` to nested path while already in a subdirectory

**Count:** 3 occurrences

**Error:**
```
cd apps/agent-worker
cd : Cannot find path '...\apps\business-api\apps\agent-worker' because it does not exist.

cd services/policy-service
cd : Cannot find path '...\apps\business-api\services\policy-service' because it does not exist.
```

**Current directory at time of error:** `apps\business-api`  
**Attempted path:** `apps/agent-worker` (relative from subdir → resolves to `apps\business-api\apps\agent-worker` — doesn't exist)

**Root cause:**  
The `cd` command was run from inside `apps\business-api\`. All relative paths resolve from the current directory. When you are already inside a subdirectory, you must either:
- `cd ..\..\apps\agent-worker` (navigate up then into target)
- `cd C:\Users\Chouqib Saad\Desktop\telecom-ai-agent-platform\apps\agent-worker` (absolute path)

---

## ERROR 4 — `docker compose` run from wrong directory

**Count:** 2 occurrences

**Error:**
```
CreateFile C:\Users\Chouqib Saad\Desktop\telecom-ai-agent-platform\apps\business-api\infra\docker-compose\docker-compose.yml:
The system cannot find the path specified.
```

**Current directory at time of error:** `apps\business-api`  
**Command:** `docker compose -f infra/docker-compose/docker-compose.yml up -d`

**Root cause:**  
The relative path `infra/docker-compose/docker-compose.yml` is only valid from the **project root**. From inside `apps\business-api\`, the file is at `..\..\infra\docker-compose\docker-compose.yml`.

**Correct command (from project root):**
```powershell
cd C:\Users\Chouqib Saad\Desktop\telecom-ai-agent-platform
docker compose -f infra/docker-compose/docker-compose.yml up -d
```

---

## ERROR 5 — Agent-worker `python src/server.py dev` from wrong directory

**Count:** 1 occurrence

**Error:**
```
python src/server.py dev
C:\Python312\python.exe: can't open file
'C:\Users\Chouqib Saad\Desktop\telecom-ai-agent-platform\apps\business-api\src\server.py':
[Errno 2] No such file or directory
```

**Current directory:** `apps\business-api` (does not have `src/server.py` — that is in `apps\agent-worker\src\`)

**Root cause:**  
The `src/server.py` path is relative to `apps\agent-worker\`, not `apps\business-api\`.

**Correct command:**
```powershell
cd C:\Users\Chouqib Saad\Desktop\telecom-ai-agent-platform\apps\agent-worker
python src/server.py start
```

---

## ERROR 6 — `ModuleNotFoundError: No module named 'sqlalchemy'` in business-api

**Count:** 2 occurrences

**Error:**
```
ModuleNotFoundError: No module named 'sqlalchemy'
```

**Full traceback:**
```
Process SpawnProcess-1:
  File "C:\Python312\Lib\multiprocessing\process.py", line 314, in _bootstrap
  File "C:\Python312\Lib\multiprocessing\process.py", line 108, in run
  File ".venv\Lib\site-packages\uvicorn\_subprocess.py", line 80, in subprocess_started
  File ".venv\Lib\site-packages\uvicorn\server.py", line 66, in run
  File ".venv\Lib\site-packages\uvicorn\importer.py", line 19, in import_from_string
  File "apps\business-api\src\business_api\main.py", line 12, in <module>
    from sqlalchemy.orm import Session
```

**Failing file & line:**  
`apps\business-api\src\business_api\main.py:12`
```python
from sqlalchemy.orm import Session
```

**Root cause:**  
`business-api` imports `sqlalchemy.orm.Session` directly at line 12 of `main.py`, but its `pyproject.toml` (`apps\business-api\pyproject.toml:6-12`) does **not** declare `sqlalchemy` as a direct dependency:

```toml
dependencies = [
  "object-storage",
  "fastapi==0.115.6",
  "uvicorn[standard]==0.34.0",
  "audit-trail",
  "persistence",
]
```

`sqlalchemy` comes **transitively** through `persistence` (which declares `sqlalchemy>=2.0,<2.1`). If `persistence` was not `pip install`ed into the venv before running `business_api`, the transitive dependency is not resolved.

**The same direct-import-without-direct-dependency pattern also exists in:**
| File | Line | Import |
|---|---|---|
| `apps\business-api\src\business_api\main.py` | 12 | `from sqlalchemy.orm import Session` |
| `apps\business-api\src\business_api\repositories.py` | 4-5 | `from sqlalchemy import func, select; from sqlalchemy.orm import Session` |
| `apps\business-api\src\business_api\jobs\integrity.py` | 10-11 | `from sqlalchemy import func, select; from sqlalchemy.orm import Session` |
| `apps\business-api\src\business_api\jobs\retention.py` | 12-13 | `from sqlalchemy import select, update; from sqlalchemy.orm import Session` |
| `services\policy-service\src\policy_service\main.py` | 7 | `from sqlalchemy.orm import Session` |
| `services\policy-service\src\policy_service\service.py` | 10 | `from sqlalchemy.orm import Session` |
| `services\execution-service\src\execution_service\main.py` | 7 | `from sqlalchemy.orm import Session` |
| `services\execution-service\src\execution_service\service.py` | 12-14 | `from sqlalchemy import select; from sqlalchemy.exc import IntegrityError; from sqlalchemy.orm import Session` |
| `services\execution-service\src\execution_service\projections.py` | 14-15 | `from sqlalchemy import select; from sqlalchemy.orm import Session` |
| `services\context-service\src\context_service\main.py` | 11 | `from sqlalchemy.orm import Session` |
| `services\context-service\src\context_service\repositories.py` | 8-9 | `from sqlalchemy import select; from sqlalchemy.orm import Session` |

These files all directly import `sqlalchemy` classes without `sqlalchemy` being listed as a direct dependency in their respective `pyproject.toml`. They rely on the transitive dependency through `persistence`, which works **only after** `pip install ./packages/persistence` (and all other shared packages) has been run.

---

## ERROR 7 — `ModuleNotFoundError: No module named 'service_auth'` in policy-service

**Count:** 1 occurrence

**Error:**
```
ModuleNotFoundError: No module named 'service_auth'
```

**Full traceback:**
```
File "services\policy-service\src\policy_service\main.py", line 6, in <module>
    from service_auth import require_internal_key
```

**Failing file & line:**  
`services\policy-service\src\policy_service\main.py:6`
```python
from service_auth import require_internal_key
```

**Root cause:**  
Unlike `sqlalchemy`, `service_auth` IS properly declared in `policy-service/pyproject.toml`:

```toml
dependencies = [
  "service-auth",    # ✓ present
  ...
]
```

However, `pip install ./packages/service-auth` was **not** run before the attempt to start policy-service. The shared packages (Step 2 of the one-time setup) must all be installed first.

**All services that import `service_auth` and could fail identically if not installed:**
| File | Line | Service |
|---|---|---|
| `services\policy-service\src\policy_service\main.py` | 6 | policy-service |
| `services\context-service\src\context_service\main.py` | 10 | context-service |
| `services\decision-service\src\decision_service\main.py` | 6 | decision-service |
| `services\execution-service\src\execution_service\main.py` | 6 | execution-service |
| `services\knowledge-service\src\knowledge_service\main.py` | 6 | knowledge-service |
| `services\notification-service\src\notification_service\main.py` | 6 | notification-service |

---

## ERROR SUMMARY TABLE

| # | Error | Category | Affected File(s) | Root Cause |
|---|---|---|---|---|
| 1 | `&&` not valid in PowerShell | **Shell syntax** | User's terminal | Provided commands used bash syntax on Windows PowerShell |
| 2 | `.venv` activation from subdir | **Working directory** | User's terminal | `.venv` is at project root; relative path fails from subdirectories |
| 3 | `cd` to nested path from subdir | **Working directory** | User's terminal | Relative `cd` resolves from current subdirectory, not project root |
| 4 | `docker compose` from wrong dir | **Working directory** | User's terminal | Relative path `infra/...` resolves from `apps\business-api\` |
| 5 | `python src/server.py` from wrong dir | **Working directory** | User's terminal | `src/server.py` is in `apps\agent-worker\`, not `apps\business-api\` |
| 6 | `No module named 'sqlalchemy'` | **Missing dependency** | `apps\business-api\src\business_api\main.py:12` (and 11 other files) | Direct import of sqlalchemy without direct dependency declaration; transitive only |
| 7 | `No module named 'service_auth'` | **Missing installation** | `services\policy-service\src\policy_service\main.py:6` | `pip install ./packages/service-auth` not run before uvicorn |

**Total distinct errors:** 7  
**Total occurrences:** 22