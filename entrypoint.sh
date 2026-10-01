#!/bin/sh
set -e
# 1) bring the database schema up to date, 2) start the production server
alembic upgrade head
exec gunicorn "app.main:create_app()" \
  -k uvicorn_worker.UvicornWorker \
  -w "${WEB_CONCURRENCY:-2}" \
  -b "0.0.0.0:${PORT:-8000}" \
  --access-logfile -
