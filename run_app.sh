#!/bin/bash
cd "$(dirname "$0")"
if [ ! -f models/lmp_model/lmp_model.pt ]; then
  echo "Trained model not found at models/lmp_model/lmp_model.pt"
  echo "Download the 'lmp_model' folder from Google Drive (My Drive > judgebert_final) into models/"
  exit 1
fi
if [ ! -d .venv ]; then
  echo "First run: creating a Python environment and installing packages (5-10 minutes)..."
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip -q
  ./.venv/bin/pip install -r requirements-app.txt
fi
echo "Starting the app... open http://localhost:8000 (Ctrl+C to stop)"
(sleep 8 && open http://localhost:8000 >/dev/null 2>&1) &
./.venv/bin/python -m uvicorn app.server:app --port 8000
