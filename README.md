# Task Manager

Production-ready full-stack task manager with React, FastAPI, PostgreSQL, Docker, and GitHub Actions CI.

## Features

- User registration and JWT authentication
- Create, update, delete, and complete tasks
- Search and filter tasks by status
- User-specific task lists

## Tech Stack

- **Frontend:** React + Vite
- **Backend:** FastAPI + SQLAlchemy + Alembic
- **Database:** PostgreSQL
- **Containers:** Docker + Docker Compose
- **CI/CD:** GitHub Actions

## Quick Start (Docker)

```bash
docker compose up --build
```

| Service  | URL                    |
|----------|------------------------|
| Frontend | http://localhost:3000  |
| Backend  | http://localhost:8000  |
| API docs | http://localhost:8000/docs |

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Frontend dev server: http://localhost:5173

## API Endpoints

| Method | Endpoint                  | Description              |
|--------|---------------------------|--------------------------|
| POST   | `/api/auth/register`      | Register user            |
| POST   | `/api/auth/login`         | Login (OAuth2 form)      |
| GET    | `/api/auth/me`            | Current user             |
| GET    | `/api/tasks`              | List tasks (`?search=`, `?completed=`) |
| POST   | `/api/tasks`              | Create task              |
| PUT    | `/api/tasks/{id}`         | Update task              |
| PATCH  | `/api/tasks/{id}/complete`| Mark task complete       |
| DELETE | `/api/tasks/{id}`         | Delete task              |

## Testing

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm run lint && npm run build
```

## Project Structure

```
task-manager-devops/
├── frontend/          # React app
├── backend/           # FastAPI app
├── .github/workflows/ # CI pipelines
└── docker-compose.yml
```

## Environment Variables

### Backend (`backend/.env`)

- `DATABASE_URL` — PostgreSQL connection string
- `SECRET_KEY` — JWT signing key
- `CORS_ORIGINS` — Comma-separated allowed origins

### Frontend (`frontend/.env`)

- `VITE_API_URL` — Backend API base URL

## CI/CD

GitHub Actions runs on push/PR to `main`:

- Backend: `ruff check` + `pytest`
- Frontend: `eslint` + `vite build`

Pipeline fails if any check fails.
