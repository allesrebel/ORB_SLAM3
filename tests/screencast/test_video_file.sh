#!/usr/bin/env bash
# test_video_file.sh — Test 1: feed SLAM frames decoded from an on-disk video.
#
# Uses mono_screencast_stream (cv::VideoCapture) to decode the screencast .mp4
# in-process — no separate ffmpeg frame-extraction step. Verifies SLAM finishes,
# produces a non-empty map, and the resulting trajectory looks sane.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
. "${SCRIPT_DIR}/common.sh"

OUT_DIR="${1:-${REPO_ROOT}/test_data/test_video_file}"
mkdir -p "$OUT_DIR"

require_cmd ffprobe
require_bin "$SLAM_STREAM_BIN"
[[ -f "$VOCAB"    ]] || { red "Vocabulary missing: $VOCAB"; exit 1; }
[[ -f "$SETTINGS" ]] || { red "Settings missing: $SETTINGS"; exit 1; }

section "Test 1 — video file decode"
ensure_test_video

note "Decoding $TEST_VIDEO via cv::VideoCapture"
pushd "$OUT_DIR" >/dev/null
    rm -f run.log KeyFrameTrajectory.txt Map.ply *.txt 2>/dev/null
    set +e
    "$SLAM_STREAM_BIN" "$VOCAB" "$SETTINGS" "$TEST_VIDEO" 0 \
        2>&1 | tee run.log
    rc=${PIPESTATUS[0]}
    set -e
popd >/dev/null

if [[ $rc -ne 0 ]]; then
    red "mono_screencast_stream exited $rc"
    exit $rc
fi

KFs=$(parse_kfs "${OUT_DIR}/run.log")
MPs=$(parse_mps "${OUT_DIR}/run.log")
note "SLAM map: KFs=${KFs:-?}, MPs=${MPs:-?}"

section "Trajectory validation"
"$VALIDATE" "${OUT_DIR}/KeyFrameTrajectory.txt" 5 0.001
green "Test 1 PASS — file-decode SLAM mapped ${KFs} KFs / ${MPs} MPs."
echo "Outputs: $OUT_DIR"
