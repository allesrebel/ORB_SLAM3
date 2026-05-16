#!/usr/bin/env bash
# reproduce.sh
# Verifies the reproducibility of the UI State Mapping experiments.

set -euo pipefail

# The exact commit used for the research report
ORB_COMMIT="165cd137f62316c77541fe28d18cb06a5ede0551"
ORB_REPO="https://github.com/allesrebel/ORB_SLAM3.git"
CLONE_DIR="/tmp/reproduce_orb_slam3"
VENV_DIR="/tmp/reproduce_venv"

export RUNS_ROOT="/tmp/reproduce_runs"
export VIDEOCUA_ROOT="/tmp/reproduce_videocua"

# Get absolute path to the saved data in this repo
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORIGINAL_CSV="${REPO_DIR}/experiment_data/final_results.csv"

echo "============================================================"
echo " Topo-SLAM Reproducibility Verification Script"
echo "============================================================"

# 1. Setup Python Env
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/5] Setting up Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
export PYTHON_BIN="${VENV_DIR}/bin/python"
"$PYTHON_BIN" -m pip install -q pandas torch torchvision transformers Pillow opencv-python optuna

# 2. Clone ORB_SLAM3
if [ ! -d "$CLONE_DIR" ]; then
    echo "[2/5] Cloning ORB_SLAM3 repository..."
    git clone "$ORB_REPO" "$CLONE_DIR"
fi

cd "$CLONE_DIR"
echo "[3/5] Checking out research commit: $ORB_COMMIT"
git fetch origin || true
git checkout "$ORB_COMMIT"

# 3. Build ORB_SLAM3
echo "[4/5] Building ORB_SLAM3 (this may take a while)..."
# Check if already built
if [ ! -f "Examples/Monocular/mono_topological_screencast" ]; then
    ./build.sh > build_log.txt 2>&1 || { echo "Build failed! See $CLONE_DIR/build_log.txt"; exit 1; }
else
    echo "  -> Found existing binaries, skipping build."
fi

# 4. Run the experiment script
echo "[5/5] Running the evaluation pipeline..."
chmod +x scripts/research_eval/run_research.sh
./scripts/research_eval/run_research.sh

# 5. Verify Results
echo "============================================================"
echo "Verification Complete!"
echo "Comparing newly generated results with saved repository data:"
NEW_CSV="${RUNS_ROOT}/final_results.csv"

if diff -q "$ORIGINAL_CSV" "$NEW_CSV" > /dev/null; then
    echo "SUCCESS: Newly generated results exactly match the saved experimental data."
else
    echo "WARNING: Newly generated results differ from saved data. (Note: slight latency differences and VLM mock randomness are expected)."
    diff -y "$ORIGINAL_CSV" "$NEW_CSV" || true
fi
echo "============================================================"