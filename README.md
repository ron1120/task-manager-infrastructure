# Task Manager — API & JWT

A full-stack task manager built to demonstrate **REST API calls** and **JWT authentication**.

The backend (FastAPI) is the source of truth. The React UI is one client that calls the same HTTP endpoints you can use with `curl`, Postman, or Swagger.

| Service  | URL                         |
|----------|-----------------------------|
| Frontend | http://localhost:3000       |
| API      | http://localhost:8000       |
| Swagger  | http://localhost:8000/docs  |
| Health   | http://localhost:8000/health |

---

## Auth model (JWT)

This app uses **stateless JWT Bearer tokens** (not cookies, not server sessions).

```text
1. POST /api/auth/register     → create user (password is hashed with bcrypt)
2. POST /api/auth/login        → verify password → return access_token (JWT)
3. Client stores the JWT       → localStorage (frontend) or env var (curl)
4. Later requests              → Authorization: Bearer <access_token>
5. Backend decodes JWT         → loads user → allows or rejects (401)
```

### What’s inside the JWT

| Claim | Meaning |
|-------|---------|
| `sub` | User id (string) |
| `exp` | Expiry time (UTC) |

Signed with `SECRET_KEY` using `HS256`. Default lifetime: **60 minutes** (`ACCESS_TOKEN_EXPIRE_MINUTES`).

### Protected vs public routes

| Public (no token) | Protected (Bearer required) |
|-------------------|-----------------------------|
| `GET /health` | `GET /api/auth/me` |
| `POST /api/auth/register` | All `/api/tasks...` |
| `POST /api/auth/login` | |

Missing / invalid / expired token → **401 Unauthorized**.

---

## Quick start (Docker)

```bash
docker compose up --build
```

Then open Swagger: http://localhost:8000/docs

---

## Chat bot for this repo (pagewise)

An optional extra container, [pagewise](https://github.com/rronss/pagewise), runs a RAG chat bot that answers
questions about this repository: the API and JWT flow, the Docker setup, Terraform, Ansible and CI. It reads the
repo's Markdown, code and config files (never `.env`, keys or Terraform state), and every answer shows the file
and line range it came from, with a link. Anything the files don't cover is refused instead of guessed.

```bash
echo 'ANTHROPIC_API_KEY=your-key' > .env      # .env is git-ignored
docker compose --profile assistant up --build
```

Open http://localhost:3000 and click the round chat button in the bottom-right corner (it appears on every page).
The bot runs in its own container; the frontend's nginx forwards `/assistant/` to it (`frontend/nginx.conf`), so
the browser only talks to one origin. Without `--profile assistant` nothing changes: the container does not start and
the button stays hidden. The bot's own page and API are also at http://localhost:8010. While developing pagewise
itself, build from a local checkout with `PAGEWISE_SRC=../pagewise docker compose --profile assistant up --build`.

---

## Incident tracker (DevOps and security operations)

Besides tasks, the app is an incident and alert tracker: failed CI runs, Prometheus alerts and anything else that can
send JSON become **incidents** with a severity, a deadline (SLA), an owner and a timeline. Open it at
http://localhost:3000/incidents.

```
GitHub Actions failure / ci-triage-agent / Alertmanager alert / any JSON    (API key, one per source)
        |
   POST /api/intake/...   ->   Incident  ->  triage, assign, comment, resolve   ->  Audit log
                                  |
                              /metrics (open incidents by severity, past SLA)  ->  Prometheus
```

**Incidents.** Severity P1 to P4 sets the deadline: P1 4 hours, P2 24 hours, P3 72 hours, P4 7 days. Status moves
`open -> triaged -> mitigated -> resolved` (a resolved incident can be reopened; other jumps return 409). The first step
out of `open` is the acknowledgement, so the dashboard shows MTTA and MTTR for the last 30 days. Every status change,
comment, assignment and severity change goes on the incident's timeline.

**Roles.** The first account created is the admin; everyone after that starts as an analyst.

| Role | Can |
|---|---|
| viewer | read incidents and stats |
| analyst | also open, update, assign, comment on and move incidents |
| admin | also manage API keys and roles, and read the audit log |

**Audit log.** Every change records who did it (a person, or `key:<name>` for a machine), what, which object, and
from which IP: incidents, API keys, role changes, logins and failed logins. Entries are only ever added; there is no
endpoint to edit or delete them. Passwords, tokens and API keys are never written to it.

**API keys.** Machines authenticate with a key created by an admin (Admin page, or `POST /api/api-keys`). The key is
shown once; only its SHA-256 is stored. Each key works for one source and can be revoked at once. Send it as
`X-API-Key: ops_...` or `Authorization: Bearer ops_...`.

| Endpoint | Source key | What it does |
|---|---|---|
| `POST /api/intake/github-actions` | `github_actions` | A failed workflow run becomes an incident (P2 on the default branch, else P3). Post GitHub's `workflow_run` event as is. |
| `POST /api/intake/alertmanager` | `alertmanager` | Firing alerts open incidents (critical P1, high or error P2, warning P3, info P4). A resolved alert moves a triaged incident to `mitigated`; a person still closes it. |
| `POST /api/intake/ci-triage` | `ci_triage` | The ci-triage-agent's diagnosis is added to the incident for that run, or opens one. |
| `POST /api/intake/scan/{trivy,gitleaks,hadolint}` | `scanner` | Scanner JSON becomes findings (see Security scanning below). |
| `POST /api/intake/generic` | `generic` | `{title, severity, service, environment, description, external_id, evidence}` |

The same event reported again (same source and id) is one incident with a higher `occurrences` count, and a repeat of a
resolved incident reopens it.

**Report CI failures from GitHub Actions.** Add this workflow to a repository you want to watch, with the secrets
`INCIDENTS_URL` and `INCIDENTS_KEY`. The event goes through an environment variable, never into the shell command, so
a branch name or commit message cannot inject commands:

```yaml
on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]
jobs:
  report:
    if: github.event.workflow_run.conclusion == 'failure'
    runs-on: ubuntu-latest
    steps:
      - env:
          URL: ${{ secrets.INCIDENTS_URL }}
          KEY: ${{ secrets.INCIDENTS_KEY }}
          EVENT: ${{ toJSON(github.event) }}
        run: |
          printf '%s' "$EVENT" | curl --fail -sS -X POST "$URL/api/intake/github-actions" \
            -H "X-API-Key: $KEY" -H "Content-Type: application/json" --data @-
```

**Turn Prometheus alerts into incidents.** The API exposes `/metrics` (request counts and latency, plus
`incidents_open{severity}` and `incidents_breached`), Prometheus loads the rules in `monitoring/alerts.yml`, and an
Alertmanager container posts alerts to the intake:

```bash
# 1. create a key with source "alertmanager" on the Admin page, then save it (the file is git-ignored)
printf '%s' 'ops_...' > monitoring/intake.key
# 2. start everything, including Alertmanager
docker compose --profile alerting up --build
```

Try it without breaking anything by sending Alertmanager a test alert:
`curl -X POST localhost:9093/api/v2/alerts -H 'Content-Type: application/json' -d '[{"labels":{"alertname":"Test","severity":"critical","service":"demo"}}]'`
and an incident opens within about 10 seconds.

**Known limits.**
- An alert about the tracker itself (for example `BackendDown`) cannot be delivered while the tracker is down.
  Alertmanager keeps retrying, but in practice route those alerts to Slack or email as well.
- `/metrics` has no login, like most exporters. Do not publish port 8000 beyond a trusted network.
- Failed logins are audited but not yet rate limited.
- Tasks, the older feature, are untouched and still work for every role.

---

## Security scanning (DevSecOps)

Every push, pull request and a weekly schedule run `.github/workflows/security.yml`, and the results land in the
findings tracker at http://localhost:3000/security.

| Check | Tool | Fails the build on |
|---|---|---|
| Leaked secrets, full git history | gitleaks (`--redact`, so the value never reaches the log) | any leak not in `.gitleaksignore` |
| Dockerfile quality | Hadolint | any warning or error |
| Python and npm dependencies | pip-audit, `npm audit --omit=dev` | known vulnerabilities (npm: high or worse) |
| Code, dependency files, Terraform, Dockerfiles | Trivy `fs` (vulnerabilities, secrets, misconfiguration) | HIGH or CRITICAL with a fix, not in `.trivyignore.yaml` |
| Both container images | Trivy `image` | HIGH or CRITICAL with a fix, not in `.trivyignore.yaml` |

Scanner versions are pinned in the workflow. A risk we have looked at and accepted goes in `.trivyignore.yaml` (or
`.gitleaksignore`) **with a reason and an expiry date**, so it comes back for a fresh decision instead of being forgotten.

**The findings tracker.** On `main` and on the weekly run the workflow also uploads the *unfiltered* scan, so an accepted
risk stays visible as accepted instead of looking fixed. Upload by hand with the same script:

```bash
INCIDENTS_URL=http://localhost:8000 INCIDENTS_KEY=ops_... \
  scripts/upload-scan.sh trivy report.json [target] [commit-sha] [run-url]     # also: gitleaks, hadolint
```

The key must have source `scanner` (Admin > API keys). In CI, add the secrets `INCIDENTS_URL` and `INCIDENTS_KEY`;
without them the upload job skips itself. The endpoint is `POST /api/intake/scan/{trivy|gitleaks|hadolint}` and takes the
scanner's own JSON, unchanged.

- **One row per problem.** The same finding in the next scan is the same row (`last seen` moves, `occurrences` goes up).
- **Fixed by itself.** A finding that is missing from a full scan of the same target is marked `fixed`; if it comes back it is
  reopened. Pass `complete=false` for a partial scan (for example one pull request) so nothing is closed by mistake.
- **Accept a risk.** An analyst accepts a finding with a written reason (at least 5 characters). It stays accepted across
  scans, and the reason, the person and the time are in the audit log. Only a scan can mark a finding fixed.
- **Incidents, only for what needs action today.** A leaked secret opens a P1 incident; new CRITICAL vulnerabilities or
  misconfigurations open a P2, once per scan. Lint and lower severities do not. Any finding can also get an incident by hand.
- **Secret values are never stored.** Parsers drop gitleaks' `Secret` and `Match`, Trivy's secret `Match`, and commit author
  names and emails before anything is written; a test searches every table to prove it. Only the rule and where it is are kept.
- `/metrics` also exports `findings_open{severity}`.

**What the scanners found here, and what changed.** The first scans reported 1,194 findings, including 8 critical.
`python-jose` had two critical CVEs in the library that signs login tokens (replaced with PyJWT); `python-multipart`, `pytest`,
`react-router-dom` and the old FastAPI/Starlette had known vulnerabilities (upgraded); the frontend image sat on an end-of-life
Alpine with 215 fixable findings (new nginx base); and the backend installed `gcc` it did not need and ran as root (both
removed). After the fixes: 0 critical, 187 open (nearly all unfixed Debian packages in the Python base image), 14 accepted
with reasons, and the build gates pass. The remaining accepted risks are listed in `.trivyignore.yaml`.

**Known limits.**
- Findings in the base image are only as fresh as the image tag; rebuilding on a newer base is how most of them close.
- The tracker matches findings by scanner, target and a fingerprint. Renaming a scan target looks like a new set of findings.
- Trivy is the only vulnerability scanner so far; the dev default `SECRET_KEY` is still short (PyJWT warns about it) and should
  be a long random value anywhere real.

---

## Learn the API with curl

Base URL: `http://localhost:8000`

### 1. Register

```bash
curl -s -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"password123"}'
```

Example response:

```json
{
  "id": 1,
  "email": "demo@example.com",
  "created_at": "2026-07-13T00:00:00Z"
}
```

Password is never returned. It is stored as a bcrypt hash in Postgres.

### 2. Login (get JWT)

Login uses **OAuth2 password form** fields (`username` + `password`). Put the email in `username`.

```bash
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo@example.com&password=password123"
```

Example response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Save the token:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo@example.com&password=password123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "$TOKEN"
```

### 3. Current user (`/me`)

```bash
curl -s http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Create a task

```bash
curl -s -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Buy milk","description":"2%"}'
```

### 5. List tasks

```bash
# all
curl -s http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN"

# only incomplete
curl -s "http://localhost:8000/api/tasks?completed=false" \
  -H "Authorization: Bearer $TOKEN"

# search
curl -s "http://localhost:8000/api/tasks?search=milk" \
  -H "Authorization: Bearer $TOKEN"
```

### 6. Update / complete / delete

```bash
# update
curl -s -X PUT http://localhost:8000/api/tasks/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Buy oat milk","completed":false}'

# mark complete
curl -s -X PATCH http://localhost:8000/api/tasks/1/complete \
  -H "Authorization: Bearer $TOKEN"

# delete
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE http://localhost:8000/api/tasks/1 \
  -H "Authorization: Bearer $TOKEN"
# → 204
```

### 7. What 401 looks like

```bash
curl -s -i http://localhost:8000/api/tasks
# HTTP/1.1 401 Unauthorized
```

---

## API reference

### Auth

| Method | Endpoint | Auth | Body | Description |
|--------|----------|------|------|-------------|
| `POST` | `/api/auth/register` | No | JSON `{email, password}` | Create account |
| `POST` | `/api/auth/login` | No | Form `username`, `password` | Return JWT |
| `GET` | `/api/auth/me` | Bearer | — | Current user |

**Register body rules:** valid email, password length 8–128.

**Login note:** OAuth2 form field is named `username`; this API expects the **email** there.

### Tasks (all require Bearer JWT)

| Method | Endpoint | Body / query | Description |
|--------|----------|--------------|-------------|
| `GET` | `/api/tasks` | `?completed=true\|false`, `?search=` | List current user’s tasks |
| `POST` | `/api/tasks` | JSON `{title, description?}` | Create task |
| `GET` | `/api/tasks/{id}` | — | Get one task (own only) |
| `PUT` | `/api/tasks/{id}` | JSON partial `{title?, description?, completed?}` | Update task |
| `PATCH` | `/api/tasks/{id}/complete` | — | Mark completed |
| `DELETE` | `/api/tasks/{id}` | — | Delete task (204) |

Tasks are always scoped to the logged-in user (`user_id` from the JWT). You cannot read or change another user’s tasks.

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/docs` | Interactive Swagger UI |
| `GET` | `/openapi.json` | OpenAPI schema (generated) |

---

## How the frontend uses the API

The React app is a JWT client:

1. Login page → `POST /api/auth/login`
2. Saves `access_token` in `localStorage` (`task_manager_token`)
3. Calls `GET /api/auth/me` to load the user
4. Every task request adds `Authorization: Bearer <token>` via `frontend/src/services/api.js`
5. Logout clears localStorage (JWT is not revoked server-side; it expires on its own)

Key files:

| File | Role |
|------|------|
| `frontend/src/services/authService.js` | register / login / me |
| `frontend/src/services/taskService.js` | task CRUD API calls |
| `frontend/src/utils/token.js` | localStorage JWT helpers |
| `frontend/src/context/AuthProvider.jsx` | auth state for the UI |
| `backend/app/core/security.py` | hash password + create/decode JWT |
| `backend/app/api/deps.py` | `get_current_user` (Bearer → User) |
| `backend/app/api/routes/auth.py` | auth endpoints |
| `backend/app/api/routes/tasks.py` | task endpoints |

---

## Local development (without Docker UI)

### Backend

Needs Postgres running (Compose `db` service, or local Postgres).

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --reload-dir app
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Dev UI: http://localhost:5173

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection string |
| `SECRET_KEY` | JWT signing secret (**change in production**) |
| `ALGORITHM` | JWT algorithm (`HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime |
| `CORS_ORIGINS` | Allowed frontend origins (comma-separated) |

### Frontend (`frontend/.env`)

| Variable | Purpose |
|----------|---------|
| `VITE_API_URL` | Backend base URL (e.g. `http://localhost:8000`) |

---

## Project structure

```text
TM-Project/
├── backend/
│   ├── app/
│   │   ├── api/routes/     # HTTP endpoints (auth, tasks)
│   │   ├── api/deps.py     # JWT → current user
│   │   ├── core/           # settings + security (JWT/bcrypt)
│   │   ├── models/         # SQLAlchemy tables
│   │   ├── schemas/        # request/response JSON shapes
│   │   ├── services/       # business logic
│   │   └── main.py         # FastAPI app
│   ├── alembic/            # DB migrations
│   └── tests/              # API tests
├── frontend/               # React client (calls the API)
├── docker-compose.yml      # db + backend + frontend
└── .github/workflows/      # CI
```

---

## Testing

```bash
# Backend API tests
cd backend && pytest

# Frontend lint + build
cd frontend && npm run lint && npm run build
```

CI (GitHub Actions) runs the same checks on push/PR to `main`.

---

## Security notes (JWT)

- Passwords are **hashed** (bcrypt), never stored plain.
- JWTs are **signed**, not encrypted — anyone can decode the payload, but cannot forge a valid token without `SECRET_KEY`.
- Do not commit a real production `SECRET_KEY`.
- Tokens in `localStorage` can be stolen via XSS — keep inputs safe; consider HttpOnly cookies for production hardening later.
- There is no server-side logout/blacklist yet: delete the token on the client, or wait for `exp`.
