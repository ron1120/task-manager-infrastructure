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
