#!/usr/bin/env bash
# run_orbslam3_on_task.sh — runs the geometric baseline and (later) the
# topological binary on one VideoCUA task.
#
# Usage:
#   run_orbslam3_on_task.sh <task_id> [--baseline-only|--topo-only] [--keep-frames]
#
# task_id is "<app>/<task>", e.g. "OnlyOffice_Forms/41765".
# Outputs land in /root/orbslam3_runs/VideoCUA/<app>/<task>/<run_id>/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

VOCAB="${REPO_ROOT}/Vocabulary/ORBvoc.txt"
SETTINGS="${SCRIPT_DIR}/VideoCUA_1080p.yaml"
BASELINE_BIN="${SCRIPT_DIR}/mono_screencast_images"
TOPO_BIN="${SCRIPT_DIR}/mono_topological_screencast"

VIDEOCUA_ROOT="${VIDEOCUA_ROOT:-/root/VideoCUA}"
RUNS_ROOT="${RUNS_ROOT:-/root/orbslam3_runs/VideoCUA}"
PYTHON_BIN="${PYTHON_BIN:-/root/.venv-videocua/bin/python}"
DOWNLOAD_PY="${REPO_ROOT}/scripts/videocua/videocua_download.py"

FPS=30

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*"; }
note()  { printf '\033[0;36m  • %s\033[0m\n' "$*"; }

usage() {
    cat >&2 <<EOF
Usage: $0 <task_id> [--baseline-only|--topo-only] [--keep-frames]
   task_id has form "<app>/<task>", e.g. "OnlyOffice_Forms/41765"
EOF
    exit 1
}

[[ $# -ge 1 ]] || usage
TASK_ID="$1"; shift

if [[ "$TASK_ID" != */* ]]; then
    red "task_id must be '<app>/<task>'; got: $TASK_ID"
    exit 1
fi

RUN_BASELINE=true
RUN_TOPO=true
KEEP_FRAMES=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --baseline-only) RUN_TOPO=false ;;
        --topo-only)     RUN_BASELINE=false ;;
        --keep-frames)   KEEP_FRAMES=true ;;
        *) usage ;;
    esac
    shift
done

# Sanity checks for required artifacts.
[[ -f "$VOCAB" ]]    || { red "Missing vocab: $VOCAB"; exit 1; }
[[ -f "$SETTINGS" ]] || { red "Missing settings: $SETTINGS"; exit 1; }

if $RUN_BASELINE && [[ ! -x "$BASELINE_BIN" ]]; then
    red "Missing baseline binary: $BASELINE_BIN"
    exit 1
fi
if $RUN_TOPO && [[ ! -x "$TOPO_BIN" ]]; then
    red "Missing topo binary: $TOPO_BIN — build it first or use --baseline-only"
    exit 1
fi

# Ensure data is downloaded.
TASK_DIR="${VIDEOCUA_ROOT}/${TASK_ID}"
VIDEO="${TASK_DIR}/video/video.mp4"
if [[ ! -f "$VIDEO" ]]; then
    blue "[setup] Downloading $TASK_ID"
    "$PYTHON_BIN" "$DOWNLOAD_PY" --task-id "$TASK_ID"
fi
[[ -f "$VIDEO" ]] || { red "Video still missing: $VIDEO"; exit 1; }

# Per-run output dir.
RUN_ID="$(date +%Y-%m-%d_%H-%M-%S)"
RUN_DIR="${RUNS_ROOT}/${TASK_ID}/${RUN_ID}"
FRAMES_DIR="${RUN_DIR}/frames"
BASELINE_DIR="${RUN_DIR}/baseline"
TOPO_DIR="${RUN_DIR}/topological"
mkdir -p "$FRAMES_DIR" "$BASELINE_DIR" "$TOPO_DIR"

#---------------------------------------------------------------------------
# Step 1 — extract frames.
#---------------------------------------------------------------------------
blue "[1/3] Extracting frames -> $FRAMES_DIR"
ffmpeg -hide_banner -loglevel error \
    -i "$VIDEO" -vf "fps=${FPS}" -start_number 1 \
    "${FRAMES_DIR}/frame_%05d.png"
n_frames=$(find "$FRAMES_DIR" -maxdepth 1 -name 'frame_*.png' | wc -l)
note "Extracted ${n_frames} frames"
if [[ "$n_frames" -lt 60 ]]; then
    red "Too few frames extracted (${n_frames}) — refusing to run SLAM"
    exit 1
fi

#---------------------------------------------------------------------------
# Step 2 — baseline.
#---------------------------------------------------------------------------
baseline_rc=0
if $RUN_BASELINE; then
    blue "[2/3] Running mono_screencast_images (baseline)"
    pushd "$BASELINE_DIR" >/dev/null
        set +e
        "$BASELINE_BIN" "$VOCAB" "$SETTINGS" "$FRAMES_DIR" "$FPS" \
            2>&1 | tee "${BASELINE_DIR}/run.log"
        baseline_rc=${PIPESTATUS[0]}
        set -e
    popd >/dev/null
    note "baseline exit=${baseline_rc}"
else
    note "[2/3] baseline skipped"
fi

#---------------------------------------------------------------------------
# Step 3 — topological.
#---------------------------------------------------------------------------
topo_rc=0
if $RUN_TOPO; then
    blue "[3/3] Running mono_topological_screencast"
    pushd "$TOPO_DIR" >/dev/null
        set +e
        "$TOPO_BIN" "$VOCAB" "$SETTINGS" "$FRAMES_DIR" "$FPS" --out "$TOPO_DIR" \
            2>&1 | tee "${TOPO_DIR}/run.log"
        topo_rc=${PIPESTATUS[0]}
        set -e
    popd >/dev/null
    note "topo exit=${topo_rc}"
else
    note "[3/3] topo skipped"
fi

# Cleanup frames unless asked to keep.
if ! $KEEP_FRAMES; then
    rm -rf "$FRAMES_DIR"
fi

# Summary line consumed by batch_run.sh.
n_places=0; n_edges=0
if [[ -f "${TOPO_DIR}/place_graph.json" ]]; then
    n_places=$(jq '.places | length' "${TOPO_DIR}/place_graph.json")
    n_edges=$(jq  '.edges  | length' "${TOPO_DIR}/place_graph.json")
fi

green "DONE task=${TASK_ID} run_id=${RUN_ID} baseline_rc=${baseline_rc} topo_rc=${topo_rc} places=${n_places} edges=${n_edges}"
exit 0
