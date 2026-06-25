#!/bin/bash
set -o errexit

echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Initializing database..."
python -c "from database import init_db; init_db()"

echo "Starting application..."
uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}
