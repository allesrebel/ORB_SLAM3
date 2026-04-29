# common.sh — shared helpers for screencast tests. Source, don't execute.

if [[ -z "${REPO_ROOT:-}" ]]; then
    echo "common.sh: REPO_ROOT is required" >&2
    return 1 2>/dev/null || exit 1
fi

VOCAB="${REPO_ROOT}/Vocabulary/ORBvoc.txt"
SETTINGS="${REPO_ROOT}/Examples/Monocular/ScreenCapture.yaml"
GEN_BIN="${REPO_ROOT}/Examples/Monocular/gen_screencast_video"
SLAM_IMAGES_BIN="${REPO_ROOT}/Examples/Monocular/mono_screencast_images"
SLAM_STREAM_BIN="${REPO_ROOT}/Examples/Monocular/mono_screencast_stream"
SLAM_X11_BIN="${REPO_ROOT}/Examples/Monocular/mono_screencast"
VALIDATE="${REPO_ROOT}/tests/screencast/validate_trajectory.sh"

# Test video lives in test_data (shared between tests; generated once).
TEST_VIDEO="${REPO_ROOT}/test_data/screencast_test.mp4"

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
blue()   { printf '\033[0;34m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
note()   { printf '\033[0;36m  • %s\033[0m\n' "$*"; }
section(){ printf '\n\033[1;34m=== %s ===\033[0m\n' "$*"; }

require_bin() {
    if [[ ! -x "$1" ]]; then
        red "Missing binary: $1"
        red "(build it with:  cd build && make -j\$(nproc) gen_screencast_video mono_screencast_images mono_screencast_stream mono_screencast)"
        exit 1
    fi
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        red "Missing command: $1"
        exit 1
    fi
}

# Generate (or re-use) the synthetic test video.
ensure_test_video() {
    if [[ -f "$TEST_VIDEO" ]] && ffprobe -v error -i "$TEST_VIDEO" >/dev/null 2>&1; then
        local nb
        nb=$(ffprobe -v error -select_streams v:0 -count_packets \
                     -show_entries stream=nb_read_packets \
                     -of csv=p=0 "$TEST_VIDEO" 2>/dev/null || echo 0)
        if [[ "${nb:-0}" -gt 30 ]]; then
            note "Re-using $TEST_VIDEO (${nb} packets)"
            return 0
        fi
    fi
    require_bin "$GEN_BIN"
    note "Generating synthetic screencast video"
    "$GEN_BIN" "$TEST_VIDEO" 1280 720 30 12
}

# Pull the per-map KFs/MPs counts from a SLAM run log.
parse_kfs() { awk -F: '/KFs in map:/ {gsub(" ","",$2); print $2}' "$1" | tail -1; }
parse_mps() { awk -F: '/MPs in map:/ {gsub(" ","",$2); print $2}' "$1" | tail -1; }
