DATABASE_URL ?= sqlite:///$(PWD)/ueba.db
export DATABASE_URL

.PHONY: help setup venv install db-upgrade db-downgrade db-migrate db-reset db-shell run-api clean

help:
    @echo "UEBA Project - Available commands:"
    @echo ""
    @echo "  make setup       - Create virtual environment and install dependencies"
    @echo "  make install     - Install dependencies in existing environment"
    @echo "  make db-upgrade  - Run database migrations (alembic upgrade head)"
    @echo "  make db-downgrade - Rollback last migration"
    @echo "  make db-migrate  - Generate a new migration (use MSG='description')"
    @echo "  make db-reset    - Reset database (drop and recreate all tables)"
    @echo "  make db-shell    - Open SQLite shell to inspect database"
    @echo "  make run-api     - Start the API server (uvicorn)"
    @echo "  make clean       - Remove virtual environment and database files"
    @echo ""

setup: venv install

venv:
    @echo "Creating virtual environment..."
    python3 -m venv venv

install:
    @echo "Installing dependencies..."
    . venv/bin/activate && pip install --upgrade pip
    . venv/bin/activate && pip install SQLAlchemy==2.0.22 alembic==1.12.1 python-dotenv==1.0.0

db-upgrade:
    @echo "Running database migrations..."
    . venv/bin/activate && alembic upgrade head

db-downgrade:
    @echo "Rolling back last migration..."
    . venv/bin/activate && alembic downgrade -1

db-migrate:
    @echo "Generating new migration..."
    @if [ -z "$(MSG)" ]; then \
        echo "Error: Please provide a message with MSG='your message'"; \
        exit 1; \
    fi
    . venv/bin/activate && alembic revision --autogenerate -m "$(MSG)"

db-reset:
    @echo "Resetting database..."
    rm -f ueba.db
    . venv/bin/activate && alembic upgrade head

db-shell:
    @echo "Opening database shell (use .exit to quit)..."
    sqlite3 ueba.db

run-api:
    @echo "Starting API server..."
    . venv/bin/activate && uvicorn ueba.api.main:app --reload

clean:
    @echo "Cleaning up..."
    rm -rf venv
    rm -f ueba.db
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
