#!/usr/bin/env bash
# test_x11_session.sh — Test 3: end-to-end X11 capture pipeline.
#
# Boots a private Xvfb display, plays the synthetic screencast video on it
# fullscreen, jiggles the mouse cursor with xdotool, runs mono_screencast
# against that display, and verifies SLAM produces a sane trajectory.
#
# This exercises the X11 ScreenCapture wrapper end-to-end without depending
# on a real desktop session.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
. "${SCRIPT_DIR}/common.sh"

OUT_DIR="${1:-${REPO_ROOT}/test_data/test_x11_session}"
DISP="${SCREENCAST_X11_DISPLAY:-:99}"
WIDTH="${SCREENCAST_WIDTH:-1280}"
HEIGHT="${SCREENCAST_HEIGHT:-720}"
RUN_SECONDS="${SCREENCAST_X11_SECONDS:-25}"

mkdir -p "$OUT_DIR"

require_cmd Xvfb
require_cmd xdotool
require_cmd mpv
require_bin "$SLAM_X11_BIN"
[[ -f "$VOCAB"    ]] || { red "Vocabulary missing: $VOCAB"; exit 1; }
[[ -f "$SETTINGS" ]] || { red "Settings missing: $SETTINGS"; exit 1; }

section "Test 3 — X11 (Xvfb) capture pipeline"
ensure_test_video

# Track every background process we spawn so we can clean up safely.
PIDS=()
cleanup() {
    set +e
    for p in "${PIDS[@]}"; do
        kill "$p" 2>/dev/null
    done
    sleep 0.2
    for p in "${PIDS[@]}"; do
        kill -9 "$p" 2>/dev/null
    done
    wait 2>/dev/null
    # Remove the Xvfb lockfile (Xvfb cleans /tmp/.X{N}-lock on graceful exit;
    # this is a belt-and-braces cleanup for kill -9 paths).
    local n="${DISP#:}"
    rm -f "/tmp/.X${n}-lock" 2>/dev/null
}
trap cleanup EXIT

note "Starting Xvfb on ${DISP} (${WIDTH}x${HEIGHT}x24)"
Xvfb "$DISP" -screen 0 "${WIDTH}x${HEIGHT}x24" \
     -nolisten tcp -ac >"${OUT_DIR}/xvfb.log" 2>&1 &
PIDS+=($!)

# Wait for the X server to be ready before launching anything that needs it.
for i in 1 2 3 4 5 6 7 8 9 10; do
    if DISPLAY="$DISP" xdpyinfo >/dev/null 2>&1; then
        break
    fi
    sleep 0.3
done
if ! DISPLAY="$DISP" xdpyinfo >/dev/null 2>&1; then
    red "Xvfb on ${DISP} did not become ready"
    cat "${OUT_DIR}/xvfb.log" >&2
    exit 1
fi
note "Xvfb is up"

note "Playing $TEST_VIDEO fullscreen on ${DISP} (looped)"
DISPLAY="$DISP" mpv \
    --no-config --no-terminal --no-osc --no-osd-bar \
    --loop=inf --really-quiet --no-audio \
    --vo=x11 --geometry=${WIDTH}x${HEIGHT}+0+0 \
    --no-input-default-bindings --no-input-vo-keyboard \
    --keep-open=no --idle=no --fs \
    "$TEST_VIDEO" \
    >"${OUT_DIR}/mpv.log" 2>&1 &
PIDS+=($!)

# Mouse-jiggler — moves the X11 pointer in a slow figure-eight so the X11
# capture sees cursor motion on top of the playing video.
(
    DISPLAY="$DISP"; export DISPLAY
    cx=$((WIDTH / 2)); cy=$((HEIGHT / 2))
    while true; do
        for t in $(seq 0 36); do
            angle=$(awk -v t="$t" 'BEGIN{print t*10*3.14159/180}')
            mx=$(awk -v cx="$cx" -v a="$angle" 'BEGIN{print int(cx + 200*sin(a))}')
            my=$(awk -v cy="$cy" -v a="$angle" 'BEGIN{print int(cy + 80*sin(2*a))}')
            xdotool mousemove "$mx" "$my" 2>/dev/null || true
            sleep 0.1
        done
    done
) >/dev/null 2>&1 &
PIDS+=($!)

# Give the player a moment to decode the first frames before SLAM starts.
sleep 1.2

note "Running mono_screencast against ${DISP} for ${RUN_SECONDS}s"
pushd "$OUT_DIR" >/dev/null
    rm -f run.log KeyFrameTrajectory.txt Map.ply *.txt 2>/dev/null
    set +e
    timeout --signal=INT --kill-after=5s "${RUN_SECONDS}s" \
        "$SLAM_X11_BIN" "$VOCAB" "$SETTINGS" "$DISP" \
        2>&1 | tee run.log
    rc=${PIPESTATUS[0]}
    set -e
popd >/dev/null

# `timeout` exits 124 when it had to send SIGINT, which is the expected path
# (Ctrl+C is the only normal way to stop mono_screencast). Treat that as success.
if [[ $rc -ne 0 && $rc -ne 124 && $rc -ne 130 ]]; then
    red "mono_screencast exited $rc (unexpected)"
    exit $rc
fi
note "mono_screencast stopped (rc=$rc)"

section "Trajectory validation"
# The X11 path captures both the playing video AND the cursor, so the
# trajectory should still cover meaningful motion. We allow a slightly
# weaker minimum because real-time capture drops more frames than offline
# decode and the SLAM-initialisation parallax is a function of how much
# of the playing video was on screen during initialisation.
"$VALIDATE" "${OUT_DIR}/KeyFrameTrajectory.txt" 3 0.0005

KFs=$(parse_kfs "${OUT_DIR}/run.log")
MPs=$(parse_mps "${OUT_DIR}/run.log")
green "Test 3 PASS — X11 capture SLAM mapped ${KFs:-?} KFs / ${MPs:-?} MPs."
echo "Outputs: $OUT_DIR"
