#!/bin/bash
# Launcher cross-platform para a Plataforma CAM-CAD Data Frontier
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d ".venv/bin" ]; then
    PYTHON=".venv/bin/python"
elif [ -d ".venv/Scripts" ]; then
    PYTHON=".venv/Scripts/python.exe"
else
    PYTHON="python3"
fi

export PYTHONIOENCODING=utf-8
"$PYTHON" -u gui/interface_dual.py
