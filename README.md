  ![CI](https://github.com/rTIRTH/Link-Shortener/actions/workflows/ci.yml/badge.svg)

# Link Shortener

A multi-user URL shortener. Every account gets its own namespace, so
`/alice/portfolio` and `/bob/portfolio` can both exist.

**Stack:** Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic, Redis, Gunicorn, Docker,
pytest, GitHub Actions, Render.

## Features
- Register / log in (bcrypt password hashing, signed session cookies)
- Short links with random base62 codes or custom aliases, unique per user
- Optional link expiry (expired links return HTTP 410)
- Redis cache for redirects (cache hit = zero database queries) and rate limiting
- Click analytics recorded in the background: daily chart, devices, referrers
- QR code per link, and zip download of many QR codes
- CSV export (with spreadsheet-formula-injection protection) and bulk delete
- URL validation: only http/https, blocks localhost and private IPs
- Works without Redis too (it just skips caching and rate limiting)

## Run locally (no Docker)
```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env              # optional
alembic upgrade head              # creates the SQLite database
uvicorn app.main:create_app --factory --reload
```
Open http://127.0.0.1:8000

## Run with Docker (app + PostgreSQL + Redis)
```bash
docker compose up --build
```
Open http://localhost:8000

## Tests
```bash
pytest --cov=app
ruff check .
```

## Project layout
```
app/
  main.py          application factory: create_app()
  config.py        settings from environment variables
  database.py      engine + session factory
  models.py        User, Link, Click tables
  cache.py         Redis cache + rate limiter
  utils.py         slug generation and input validation
  routers/         auth.py, dashboard.py, redirect.py  (the "blueprints")
  templates/       HTML pages (Jinja2)
alembic/           database migrations
tests/             pytest suite
.github/workflows/ci.yml   CI: lint, tests, migrations on Postgres, Docker build
render.yaml        Render blueprint (web + Postgres + Redis)
```

## Deploy on Render
1. Push this repo to GitHub.
2. In Render: **New → Blueprint**, pick the repo. Render reads `render.yaml`
   and creates the web service, PostgreSQL and Redis.
3. Open the generated `onrender.com` URL once the deploy finishes.

Notes: the free web service sleeps after 15 minutes idle, and the free Postgres
database expires after 30 days (check Render's current free-tier docs).
