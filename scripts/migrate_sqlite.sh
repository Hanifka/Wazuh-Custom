#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DB_PATH="${ROOT_DIR}/ueba.db"

# Allow caller to override DATABASE_URL, otherwise default to local SQLite file.
export DATABASE_URL="${DATABASE_URL:-sqlite:///${DB_PATH}}"

if [ -f "${ROOT_DIR}/venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/venv/bin/activate"
fi

cd "${ROOT_DIR}"

alembic upgrade head
