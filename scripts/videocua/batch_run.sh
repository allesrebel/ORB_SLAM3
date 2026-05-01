#!/usr/bin/env bash
# batch_run.sh — run baseline + topo SLAM over a whitelist of VideoCUA tasks.
#
# Usage:
#   batch_run.sh --whitelist <file>
#                [--download-first | --download-jit]
#                [--baseline-only | --topo-only]
#                [--keep-frames]
#
# After all runs, refreshes the three tier whitelists in
# /root/orbslam3_runs/whitelists/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORB_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RUNNER="${ORB_ROOT}/Examples/Monocular/run_orbslam3_on_task.sh"
DOWNLOAD_PY="${SCRIPT_DIR}/videocua_download.py"
VERIFY_PY="${SCRIPT_DIR}/verify_and_whitelist.py"
PYTHON_BIN="${PYTHON_BIN:-/root/.venv-videocua/bin/python}"
SUMMARY_DIR="${SUMMARY_DIR:-/root/orbslam3_runs/batch_logs}"

WHITELIST=""
DL_MODE="jit"   # jit | first
RUN_FLAGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --whitelist)        WHITELIST="$2"; shift 2 ;;
        --download-first)   DL_MODE="first"; shift ;;
        --download-jit)     DL_MODE="jit"; shift ;;
        --baseline-only)    RUN_FLAGS+=("--baseline-only"); shift ;;
        --topo-only)        RUN_FLAGS+=("--topo-only"); shift ;;
        --keep-frames)      RUN_FLAGS+=("--keep-frames"); shift ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

[[ -n "$WHITELIST" && -f "$WHITELIST" ]] || \
    { echo "FAIL: --whitelist <file> required"; exit 1; }
[[ -x "$RUNNER" ]] || { echo "FAIL: runner not executable: $RUNNER"; exit 1; }

mapfile -t IDS < <(grep -v '^#' "$WHITELIST" | awk 'NF')
echo "Whitelist: ${WHITELIST}  (${#IDS[@]} task(s))"

mkdir -p "$SUMMARY_DIR"
RUN_ID="$(date +%Y-%m-%d_%H-%M-%S)"
SUMMARY="${SUMMARY_DIR}/${RUN_ID}.summary.tsv"
printf 'task_id\tbaseline_rc\ttopo_rc\tn_places\tn_edges\n' > "$SUMMARY"

if [[ "$DL_MODE" == "first" ]]; then
    echo "[download-first] Pre-downloading ${#IDS[@]} task(s)"
    "$PYTHON_BIN" "$DOWNLOAD_PY" --whitelist "$WHITELIST"
fi

ok=0; bad=0
for tid in "${IDS[@]}"; do
    echo "============================================================"
    echo "TASK ${tid}"
    echo "============================================================"
    if out=$("$RUNNER" "$tid" "${RUN_FLAGS[@]}" 2>&1); then
        echo "$out"
        line=$(echo "$out" | tail -1)
        b_rc=$(echo "$line" | sed -n 's/.*baseline_rc=\([0-9]*\).*/\1/p')
        t_rc=$(echo "$line" | sed -n 's/.*topo_rc=\([0-9]*\).*/\1/p')
        np=$(echo  "$line" | sed -n 's/.*places=\([0-9]*\).*/\1/p')
        ne=$(echo  "$line" | sed -n 's/.*edges=\([0-9]*\).*/\1/p')
        printf '%s\t%s\t%s\t%s\t%s\n' "$tid" "${b_rc:-?}" "${t_rc:-?}" "${np:-0}" "${ne:-0}" >> "$SUMMARY"
        ok=$((ok + 1))
    else
        echo "FAIL on ${tid}"
        printf '%s\tERROR\tERROR\t0\t0\n' "$tid" >> "$SUMMARY"
        bad=$((bad + 1))
    fi
done

echo "============================================================"
echo "Batch complete: ok=${ok} bad=${bad}"
echo "Summary: $SUMMARY"

# Refresh whitelists.
"$PYTHON_BIN" "$VERIFY_PY"
