#!/usr/bin/env bash
set -euo pipefail

echo "=== SQLAnalyst-Env Submission Validator ==="
echo ""

echo "[1/5] Checking required files..."
for f in openenv.yaml inference.py Dockerfile requirements.txt \
         app/__init__.py app/main.py app/environment.py app/models.py app/database.py \
         app/graders/__init__.py app/graders/base.py \
         app/graders/task_easy.py app/graders/task_medium.py app/graders/task_hard.py \
         app/tasks/__init__.py app/tasks/registry.py; do
    test -f "$f" || { echo "MISSING: $f"; exit 1; }
done
echo "  All required files present."

echo "[2/5] Checking inference.py is at project root..."
test -f inference.py || { echo "FAIL: inference.py must be in project root"; exit 1; }
echo "  inference.py is at root."

echo "[3/5] Checking env var usage in inference.py..."
for var in API_BASE_URL MODEL_NAME HF_TOKEN; do
    if ! grep -q "$var" inference.py; then
        echo "WARN: $var not found in inference.py"
    fi
done
echo "  Environment variables referenced."

echo "[4/5] Checking Python syntax (compileall)..."
python -m compileall -q app inference.py
echo "  All Python files compile."

echo "[5/5] Checking log format markers in inference.py..."
for marker in START STEP END; do
    if ! grep -q "\[${marker}\]" inference.py; then
        echo "FAIL: Missing [${marker}] log marker in inference.py"
        exit 1
    fi
done
echo "  Log format markers [START], [STEP], [END] present."

echo ""
echo "=== ALL CHECKS PASSED ==="
