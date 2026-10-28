#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
PYTHON_EXEC="$DIR/.venv/bin/python"
if [ ! -f "$PYTHON_EXEC" ]; then
    PYTHON_EXEC="$DIR/backend/.venv/bin/python"
fi

if [ ! -f "$PYTHON_EXEC" ]; then
    echo "Python venv not found at $PYTHON_EXEC"
    exit 1
fi

export PYTHONPATH="$DIR"
echo "Running Collivra Two-Step Email OTP Verification Tests..."
"$PYTHON_EXEC" "$DIR/scripts/run_email_otp_proofs.py"
