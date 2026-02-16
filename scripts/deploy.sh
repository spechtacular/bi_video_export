#!/bin/bash

set -e

echo "Pulling latest changes..."
git pull

echo "Activating virtualenv..."
source .venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Restarting nginx..."
brew services restart nginx

echo "Restarting dashboard..."
pkill -f run_dashboard.sh || true
nohup ./scripts/run_dashboard.sh > dashboard.log 2>&1 &

echo "Deploy complete."

