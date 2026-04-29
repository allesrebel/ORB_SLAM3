#!/usr/bin/env bash
# run_screencast_test.sh — end-to-end test for the screencast SLAM pipeline.
#
#   1. Ensure a screencast test video exists (downloads if a URL is given,
#      otherwise generates a synthetic one with gen_screencast_video).
#   2. Extract frames from the video into a sequence directory.
#   3. Run mono_screencast_images on the sequence.
#   4. Parse the output and report keyframes / map points / trajectory size.
#   5. Exit 0 only if SLAM produced a non-empty map and trajectory.
#
# Usage:
#   run_screencast_test.sh [output_dir]
#
# Environment overrides:
#   SCREENCAST_VIDEO_URL  If set, the script will curl the video from this URL
#                         instead of synthesising one. The download is verified
#                         and falls back to synthesis on failure.
#   SCREENCAST_FPS        Frame extraction rate (default 30 — matches yaml).
#   SCREENCAST_SECONDS    Synthetic video duration (default 12).
#   SCREENCAST_WIDTH      Synthetic video width (default 1280, matches yaml).
#   SCREENCAST_HEIGHT     Synthetic video height (default 720, matches yaml).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

VOCAB="${REPO_ROOT}/Vocabulary/ORBvoc.txt"
SETTINGS="${SCRIPT_DIR}/ScreenCapture.yaml"
GEN_BIN="${SCRIPT_DIR}/gen_screencast_video"
SLAM_BIN="${SCRIPT_DIR}/mono_screencast_images"

OUT_DIR="${1:-${REPO_ROOT}/test_data}"
VIDEO="${OUT_DIR}/screencast_test.mp4"
FRAMES_DIR="${OUT_DIR}/screencast_frames"
RUN_DIR="${OUT_DIR}/run"
RUN_LOG="${RUN_DIR}/run.log"

WIDTH="${SCREENCAST_WIDTH:-1280}"
HEIGHT="${SCREENCAST_HEIGHT:-720}"
FPS="${SCREENCAST_FPS:-30}"
SECONDS_DURATION="${SCREENCAST_SECONDS:-12}"

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*"; }
note()  { printf '\033[0;36m  • %s\033[0m\n' "$*"; }

require() {
    if ! command -v "$1" >/dev/null 2>&1; then
        red "Missing required command: $1"
        exit 1
    fi
}

require ffmpeg
require ffprobe

[[ -x "$SLAM_BIN" ]] || { red "mono_screencast_images not built at $SLAM_BIN"; exit 1; }
[[ -x "$GEN_BIN"  ]] || { red "gen_screencast_video not built at $GEN_BIN"; exit 1; }
[[ -f "$VOCAB"    ]] || { red "Vocabulary missing at $VOCAB"; exit 1; }
[[ -f "$SETTINGS" ]] || { red "Settings file missing at $SETTINGS"; exit 1; }

mkdir -p "$OUT_DIR" "$RUN_DIR"

#---------------------------------------------------------------------------
# Step 1 — ensure we have a screencast test video.
#---------------------------------------------------------------------------
blue "[1/4] Ensuring screencast test video is available"

need_video=true
if [[ -f "$VIDEO" ]]; then
    if ffprobe -v error -i "$VIDEO" >/dev/null 2>&1; then
        nb=$(ffprobe -v error -select_streams v:0 -count_packets \
                     -show_entries stream=nb_read_packets \
                     -of csv=p=0 "$VIDEO" 2>/dev/null || echo 0)
        if [[ "${nb:-0}" -gt 30 ]]; then
            note "Re-using existing $VIDEO (${nb} packets)"
            need_video=false
        fi
    fi
fi

if $need_video; then
    if [[ -n "${SCREENCAST_VIDEO_URL:-}" ]]; then
        note "Downloading $SCREENCAST_VIDEO_URL"
        if curl -fL --retry 2 -o "${VIDEO}.tmp" "$SCREENCAST_VIDEO_URL" \
                && ffprobe -v error -i "${VIDEO}.tmp" >/dev/null 2>&1; then
            mv "${VIDEO}.tmp" "$VIDEO"
            note "Downloaded $(stat -c%s "$VIDEO") bytes to $VIDEO"
        else
            rm -f "${VIDEO}.tmp"
            red   "Download failed — falling back to synthetic generator"
            "$GEN_BIN" "$VIDEO" "$WIDTH" "$HEIGHT" "$FPS" "$SECONDS_DURATION"
        fi
    else
        note "Generating synthetic screencast (${WIDTH}x${HEIGHT} @ ${FPS}fps, ${SECONDS_DURATION}s)"
        "$GEN_BIN" "$VIDEO" "$WIDTH" "$HEIGHT" "$FPS" "$SECONDS_DURATION"
    fi
fi

#---------------------------------------------------------------------------
# Step 2 — extract frames.
#---------------------------------------------------------------------------
blue "[2/4] Extracting frames -> $FRAMES_DIR"

rm -rf "$FRAMES_DIR"
mkdir -p "$FRAMES_DIR"
ffmpeg -hide_banner -loglevel error \
    -i "$VIDEO" -vf "fps=${FPS}" -start_number 1 \
    "${FRAMES_DIR}/frame_%05d.png"

n_frames=$(ls "$FRAMES_DIR"/frame_*.png 2>/dev/null | wc -l)
note "Extracted ${n_frames} frames"
if [[ "$n_frames" -lt 60 ]]; then
    red "Too few frames extracted (${n_frames}) — refusing to run SLAM"
    exit 1
fi

#---------------------------------------------------------------------------
# Step 3 — run SLAM.
#---------------------------------------------------------------------------
blue "[3/4] Running mono_screencast_images"

# Run from RUN_DIR so trajectory + stats files land there.
pushd "$RUN_DIR" >/dev/null
    set +e
    "$SLAM_BIN" "$VOCAB" "$SETTINGS" "$FRAMES_DIR" "$FPS" 2>&1 | tee "$RUN_LOG"
    slam_rc=${PIPESTATUS[0]}
    set -e
popd >/dev/null

if [[ "$slam_rc" -ne 0 ]]; then
    red "mono_screencast_images exited with status $slam_rc"
    exit "$slam_rc"
fi

#---------------------------------------------------------------------------
# Step 4 — report stats and verify.
#---------------------------------------------------------------------------
blue "[4/4] SLAM run summary"

frames_fed=$(awk -F: '/Frames fed:/    {gsub(" ","",$2); print $2}' "$RUN_LOG" | tail -1)
frames_failed=$(awk -F: '/Frames failed:/ {gsub(" ","",$2); print $2}' "$RUN_LOG" | tail -1)
kfs=$(awk -F: '/KFs in map:/ {gsub(" ","",$2); print $2}' "$RUN_LOG" | tail -1)
mps=$(awk -F: '/MPs in map:/ {gsub(" ","",$2); print $2}' "$RUN_LOG" | tail -1)

# SessionInfo.txt is produced by the SLAM system itself.
session_kfs=""
session_mps=""
if [[ -f "${RUN_DIR}/SessionInfo.txt" ]]; then
    session_kfs=$(awk -F: '/Number of KFs/ {gsub(" ","",$2); print $2}' "${RUN_DIR}/SessionInfo.txt" | tail -1)
    session_mps=$(awk -F: '/Number of MPs/ {gsub(" ","",$2); print $2}' "${RUN_DIR}/SessionInfo.txt" | tail -1)
fi

# KeyFrameTrajectory.txt: one line per keyframe.
traj="${RUN_DIR}/KeyFrameTrajectory.txt"
traj_lines=0
if [[ -f "$traj" ]]; then
    traj_lines=$(wc -l < "$traj")
fi

printf '\n'
printf '  %-22s %s\n' "video"             "$VIDEO"
printf '  %-22s %s\n' "frames"            "$FRAMES_DIR ($n_frames files)"
printf '  %-22s %s\n' "frames fed"        "${frames_fed:-?}"
printf '  %-22s %s\n' "frames failed"     "${frames_failed:-?}"
printf '  %-22s %s\n' "KFs (final map)"   "${kfs:-?}"
printf '  %-22s %s\n' "MPs (final map)"   "${mps:-?}"
printf '  %-22s %s\n' "KFs (SessionInfo)" "${session_kfs:-?}"
printf '  %-22s %s\n' "MPs (SessionInfo)" "${session_mps:-?}"
printf '  %-22s %s\n' "trajectory"        "${traj} (${traj_lines} keyframes)"
ply="${RUN_DIR}/Map.ply"
ply_pts=0
ply_edges=0
if [[ -f "$ply" ]]; then
    ply_pts=$(awk   '/^element vertex/ {print $3; exit}' "$ply")
    ply_edges=$(awk '/^element edge/   {print $3; exit}' "$ply")
fi
printf '  %-22s %s\n' "map (PLY)"         "${ply} (${ply_pts} verts, ${ply_edges} edges)"
printf '  %-22s %s\n' "log"               "$RUN_LOG"

# Final pass/fail.
final_kfs="${kfs:-0}"; final_mps="${mps:-0}"
if [[ "${final_kfs}" -gt 0 ]] && [[ "${final_mps}" -gt 0 ]] && [[ "${traj_lines}" -gt 0 ]]; then
    green "PASS — SLAM initialised, mapped ${final_kfs} KFs / ${final_mps} MPs over ${traj_lines} keyframes."
    exit 0
else
    red "FAIL — SLAM did not produce a valid map (KFs=${final_kfs}, MPs=${final_mps}, traj=${traj_lines})."
    exit 2
fi
