#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
PYTHON_EXEC="$DIR/backend/.venv/bin/python"

if [ ! -f "$PYTHON_EXEC" ]; then
    echo "Python venv not found at $PYTHON_EXEC"
    exit 1
fi

export PYTHONPATH="$DIR/backend"
echo "Running Collivra Two-Step Email OTP Verification Tests..."
"$PYTHON_EXEC" "$DIR/backend/run_email_otp_proofs.py"
