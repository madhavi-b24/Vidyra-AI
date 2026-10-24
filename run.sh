#!/usr/bin/env bash
# AI Teacher - Linux/macOS launcher
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "Installing dependencies (first run downloads models)..."
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env - add your FREE Gemini key from https://aistudio.google.com/app/apikey"
fi

cd backend
echo "Starting AI Teacher at http://localhost:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload