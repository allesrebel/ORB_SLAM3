#!/usr/bin/env bash
# run_all_tests.sh — drive every screencast test in sequence.
#
# Each sub-test isolates its outputs to test_data/<test_name>/. This script
# returns 0 only if every sub-test passes. Sub-tests can be filtered via
# argv: ./run_all_tests.sh file stream x11

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
. "${SCRIPT_DIR}/common.sh"

# Map shorthand → script.
declare -A TESTS=(
    [file]="${SCRIPT_DIR}/test_video_file.sh"
    [stream]="${SCRIPT_DIR}/test_video_stream.sh"
    [x11]="${SCRIPT_DIR}/test_x11_session.sh"
)
DEFAULT_ORDER=(file stream x11)

if [[ $# -gt 0 ]]; then
    SELECTED=("$@")
else
    SELECTED=("${DEFAULT_ORDER[@]}")
fi

declare -a RESULTS=()

for name in "${SELECTED[@]}"; do
    script="${TESTS[$name]:-}"
    if [[ -z "$script" ]]; then
        red "Unknown test: $name (known: ${!TESTS[*]})"
        exit 2
    fi

    section "Running: $name"
    if "$script"; then
        green "→ $name PASS"
        RESULTS+=("$name PASS")
    else
        rc=$?
        red "→ $name FAIL (rc=$rc)"
        RESULTS+=("$name FAIL(rc=$rc)")
    fi
done

section "Summary"
fail=0
for r in "${RESULTS[@]}"; do
    if [[ "$r" == *PASS* ]]; then
        green "  $r"
    else
        red   "  $r"
        fail=1
    fi
done

if [[ $fail -eq 0 ]]; then
    green "ALL TESTS PASS"
    exit 0
else
    red "ONE OR MORE TESTS FAILED"
    exit 1
fi
