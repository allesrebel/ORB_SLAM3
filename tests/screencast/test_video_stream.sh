#!/usr/bin/env bash
# test_video_stream.sh — Test 2: feed SLAM frames over a live network stream.
#
# Spawns ffmpeg as a TCP MPEG-TS server (re-encoded H.264 baseline for
# OpenCV's ffmpeg backend), connects mono_screencast_stream to it, and
# verifies SLAM still maps a sane trajectory from the streamed bytes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
. "${SCRIPT_DIR}/common.sh"

OUT_DIR="${1:-${REPO_ROOT}/test_data/test_video_stream}"
PORT="${SCREENCAST_STREAM_PORT:-23464}"
MAX_SECONDS="${SCREENCAST_STREAM_SECONDS:-10}"

mkdir -p "$OUT_DIR"

require_cmd ffmpeg
require_bin "$SLAM_STREAM_BIN"
[[ -f "$VOCAB"    ]] || { red "Vocabulary missing: $VOCAB"; exit 1; }
[[ -f "$SETTINGS" ]] || { red "Settings missing: $SETTINGS"; exit 1; }

section "Test 2 — network stream (TCP MPEG-TS, H.264)"
ensure_test_video

# Background ffmpeg as a TCP server. -listen=1 makes it block until the
# receiver connects, eliminating the start-up race.
note "Starting ffmpeg streamer on tcp://127.0.0.1:${PORT}"
(
    ffmpeg -re -stream_loop -1 -hide_banner -loglevel error \
           -i "$TEST_VIDEO" \
           -c:v libx264 -preset ultrafast -tune zerolatency \
           -g 30 -bf 0 -pix_fmt yuv420p -f mpegts \
           "tcp://127.0.0.1:${PORT}?listen=1&listen_timeout=30000000" \
           >"${OUT_DIR}/ffmpeg.log" 2>&1
) &
SENDPID=$!
trap 'kill $SENDPID 2>/dev/null || true; wait 2>/dev/null || true' EXIT

# Give ffmpeg a moment to bind the listening socket.
sleep 0.5

# OpenCV's ffmpeg backend needs more probe time to identify the H.264 stream.
export OPENCV_FFMPEG_CAPTURE_OPTIONS="analyzeduration;5000000|probesize;5000000"

note "Connecting mono_screencast_stream → tcp://127.0.0.1:${PORT}, capping at ${MAX_SECONDS}s"
pushd "$OUT_DIR" >/dev/null
    rm -f run.log KeyFrameTrajectory.txt Map.ply *.txt 2>/dev/null
    set +e
    "$SLAM_STREAM_BIN" "$VOCAB" "$SETTINGS" \
        "tcp://127.0.0.1:${PORT}" "$MAX_SECONDS" \
        2>&1 | tee run.log
    rc=${PIPESTATUS[0]}
    set -e
popd >/dev/null

# Stop the streamer cleanly.
kill $SENDPID 2>/dev/null || true
wait 2>/dev/null || true
trap - EXIT

if [[ $rc -ne 0 ]]; then
    red "mono_screencast_stream exited $rc"
    exit $rc
fi

KFs=$(parse_kfs "${OUT_DIR}/run.log")
MPs=$(parse_mps "${OUT_DIR}/run.log")
fed=$(awk -F: '/Frames fed:/ {gsub(" ","",$2); print $2}' "${OUT_DIR}/run.log" | tail -1)

note "Frames received over TCP: ${fed:-0}"
note "SLAM map: KFs=${KFs:-?}, MPs=${MPs:-?}"

section "Trajectory validation"
"$VALIDATE" "${OUT_DIR}/KeyFrameTrajectory.txt" 5 0.001
green "Test 2 PASS — stream-decode SLAM mapped ${KFs} KFs / ${MPs} MPs from ${fed} streamed frames."
echo "Outputs: $OUT_DIR"
