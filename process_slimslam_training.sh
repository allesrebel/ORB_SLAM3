#!/usr/bin/env bash
# ---------------------------------------------------------------
# make_control_files.sh
# ---------------------------------------------------------------
#  ▸ Scans every sequence in  slamslim_training_results/
#  ▸ Collects each run’s trajectory.txt (default / kp_60 / mode_1 / skip_1-6 …)
#  ▸ Copies them into a flat *_tmp/ folder using the filenames that
#    generate_control_file.py expects, e.g.:
#        MH_01_easy_default_0.txt
#        MH_01_easy_skip_3.txt
#        …
#  ▸ Looks up the matching ground-truth file in
#       evaluation/Ground_truth/EuRoC_left_cam/
#  ▸ Invokes generate_control_file.py to emit one control-file per sequence
#      →   control_files/MH_01_easy_control.txt  (etc.)
# ---------------------------------------------------------------

set -euo pipefail

# --- tweak these if your layout is different -------------------
BASE_RESULTS_DIR="slimslam_training_results"                  # raw SlimSLAM outputs
GT_DIR="evaluation/Ground_truth/EuRoC_left_cam"               # EuRoC GT poses
PY_SCRIPT="./generate_control_file.py"                        # the helper you posted
TMP_RESULTS_ROOT="./_tmp_aggregated_results"                  # working area (auto-created)
CONTROL_OUT_DIR="slimslam_control_files"                    # final control files
# ---------------------------------------------------------------

mkdir -p "$TMP_RESULTS_ROOT" "$CONTROL_OUT_DIR"

# Helper: derive EuRoC GT filename from a sequence folder name
#  MH_01_easy   ->  MH01_GT.txt
#  V1_03_difficult -> V103_GT.txt
gt_file_for_seq() {
    local seq="$1"
    IFS='_' read -r PREFIX INDEX _ <<< "$seq"   # split once: PREFIX = MH / V1 / V2 …, INDEX = 01 / 03 …
    echo "${PREFIX}${INDEX}_GT.txt"
}

# ------------------------------------------------------------------
echo "== Generating control files =="
for SEQ_PATH in "$BASE_RESULTS_DIR"/*/ ; do
    [[ -d "$SEQ_PATH" ]] || continue
    SEQ=$(basename "$SEQ_PATH")
    echo
    echo "▶ Processing sequence: $SEQ"

    # -------- assemble trajectories into a flat temp folder ----------
    TMP_DIR="$TMP_RESULTS_ROOT/$SEQ"
    rm -rf  "$TMP_DIR"
    mkdir -p "$TMP_DIR"

    for RUN_DIR in "$SEQ_PATH"*/ ; do
        [[ -d "$RUN_DIR" ]] || continue
        RUN_NAME=$(basename "$RUN_DIR")              # default | kp_60 | skip_3 …
        SRC_TRAJ="$RUN_DIR/trajectory.txt"
        [[ -f "$SRC_TRAJ" ]] || { echo "  • WARNING: missing $SRC_TRAJ, skipping"; continue; }

        if [[ "$RUN_NAME" == "default" ]]; then
            DEST_TRAJ="$TMP_DIR/${SEQ}_default_0.txt"   # baseline naming convention
        else
            DEST_TRAJ="$TMP_DIR/${SEQ}_${RUN_NAME}.txt"
        fi
        cp "$SRC_TRAJ" "$DEST_TRAJ"
    done

    # -------- work out the GT file -----------------------------------
    GT_FILE="$(gt_file_for_seq "$SEQ")"
    GT_PATH="$GT_DIR/$GT_FILE"
    if [[ ! -f "$GT_PATH" ]]; then
        echo "  • ERROR: ground-truth file not found: $GT_PATH — skipping sequence"
        continue
    fi

    # -------- run the python generator -------------------------------
    CTRL_OUT="$CONTROL_OUT_DIR/${SEQ}_control.txt"
    echo "  • Running generate_control_file.py  →  $(basename "$CTRL_OUT")"
    python3 "$PY_SCRIPT" /dev/null /dev/null "$GT_PATH" "$TMP_DIR" "$CTRL_OUT" "$SEQ"
done

echo
echo "✔  All done.  Control files are in: $CONTROL_OUT_DIR"
