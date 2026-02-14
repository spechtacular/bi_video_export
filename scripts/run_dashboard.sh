#!/bin/bash

# Get project root (directory of this script → one level up)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Activate venv
source .venv/bin/activate

# Add src to Python path
export PYTHONPATH="$PROJECT_ROOT/src"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
else
    echo ".env file not found in $PROJECT_ROOT"
fi

python -c "
from bi_exporter.dashboard.app import create_app
app = create_app()
app.run(host='127.0.0.1', port=5001)
"

