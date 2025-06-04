#!/bin/bash

# This script automates the process of generating data for the SlimSLAM controller.
# It iterates through all specified EuRoC sequences. For each sequence, it creates
# temporary YAML configuration files for different test cases (skip, kp, mode),
# runs ORB-SLAM3 for each configuration, and then moves all output artifacts into
# a dedicated folder before calling a Python script to generate the control file.
#
# USAGE:
# To execute normally:
#   ./run_slimslam_training.sh
#
# To run in "echo only" / dry-run mode:
#   ./run_slimslam_training.sh --dry-run

# --- Dry Run Mode Setup ---
DRY_RUN=false
if [ "$1" == "--dry-run" ] || [ "$1" == "dry-run" ]; then
    DRY_RUN=true
    echo "========================================"
    echo "         DRY RUN MODE ENABLED"
    echo "  Commands will be printed, not executed."
    echo "========================================"
    echo
fi

# Helper function to conditionally execute commands
function run_command() {
    if [ "$DRY_RUN" = true ]; then
        echo "[DRY RUN] Would execute: $@"
    else
        "$@"
    fi
}


# --- Configuration ---
ORB_SLAM3_BASE_PATH="${ORB_SLAM3_BASE_PATH:-.}"
EUROC_BASE_PATH="${EUROC_BASE_PATH:-./Datasets/EuRoc}"

# --- Script Variables & Pre-run Checks ---
VOC_FILE="${ORB_SLAM3_BASE_PATH}/Vocabulary/ORBvoc.txt"
BASE_TRAINING_SETTINGS_FILE="${ORB_SLAM3_BASE_PATH}/Examples/Stereo-Inertial/EuRoC_slimslam_training.yaml"
RESULTS_BASE_DIR="./slamslim_training_results"
CONTROL_FILES_BASE_DIR="./slamslim_control_files"
EXEC_FILE="${ORB_SLAM3_BASE_PATH}/Examples/Stereo-Inertial/stereo_inertial_euroc"
PYTHON_GENERATOR_SCRIPT="./generate_control_file.py"

# Check for required files individually for more specific error messages
if [ ! -f "$EXEC_FILE" ]; then
    echo "❌ ERROR: SLAM Executable not found."
    echo "   -> Searched for: $EXEC_FILE"
    exit 1
fi
if [ ! -f "$PYTHON_GENERATOR_SCRIPT" ]; then
    echo "❌ ERROR: Python generator script not found."
    echo "   -> Searched for: $PYTHON_GENERATOR_SCRIPT"
    exit 1
fi
if [ ! -f "$BASE_TRAINING_SETTINGS_FILE" ]; then
    echo "❌ ERROR: Base training settings YAML not found."
    echo "   -> Searched for: $BASE_TRAINING_SETTINGS_FILE"
    exit 1
fi

echo "✅ All required files found. Starting script..."
echo

# --- Sequence Definitions ---
SEQUENCES=(
    "MH_01_easy;Examples/Stereo-Inertial/EuRoC_TimeStamps/MH01.txt"
    "MH_02_easy;Examples/Stereo-Inertial/EuRoC_TimeStamps/MH02.txt"
    "MH_03_medium;Examples/Stereo-Inertial/EuRoC_TimeStamps/MH03.txt"
    "MH_04_difficult;Examples/Stereo-Inertial/EuRoC_TimeStamps/MH04.txt"
    "MH_05_difficult;Examples/Stereo-Inertial/EuRoC_TimeStamps/MH05.txt"
    "V1_01_easy;Examples/Stereo-Inertial/EuRoC_TimeStamps/V101.txt"
    "V1_02_medium;Examples/Stereo-Inertial/EuRoC_TimeStamps/V102.txt"
    "V1_03_difficult;Examples/Stereo-Inertial/EuRoC_TimeStamps/V103.txt"
    "V2_01_easy;Examples/Stereo-Inertial/EuRoC_TimeStamps/V201.txt"
    "V2_02_medium;Examples/Stereo-Inertial/EuRoC_TimeStamps/V202.txt"
    "V2_03_difficult;Examples/Stereo-Inertial/EuRoC_TimeStamps/V203.txt"
)

# --- Script Start ---
mkdir -p $RESULTS_BASE_DIR
mkdir -p $CONTROL_FILES_BASE_DIR

for seq_info in "${SEQUENCES[@]}"; do
    IFS=';' read -r SEQUENCE_NAME REL_TIMESTAMPS_FILE <<< "$seq_info"
    SEQUENCE_PATH="${EUROC_BASE_PATH}/${SEQUENCE_NAME}"
    TIMESTAMPS_FILE="${ORB_SLAM3_BASE_PATH}/${REL_TIMESTAMPS_FILE}"

    if [ ! -d "$SEQUENCE_PATH" ] || [ ! -f "$TIMESTAMPS_FILE" ]; then
        echo "WARNING: Data or timestamp file not found for $SEQUENCE_NAME. Skipping."
        continue
    fi

    SEQUENCE_RESULTS_DIR="$RESULTS_BASE_DIR/$SEQUENCE_NAME"
    mkdir -p $SEQUENCE_RESULTS_DIR

    echo "================================================="
    echo "Processing Sequence: $SEQUENCE_NAME"
    echo "================================================="

    TESTS=(
        "default" "skip_1;SlimSLAM.FrameSkip;1" "skip_2;SlimSLAM.FrameSkip;2"
        "skip_3;SlimSLAM.FrameSkip;3" "skip_4;SlimSLAM.FrameSkip;4" "skip_5;SlimSLAM.FrameSkip;5"
        "skip_6;SlimSLAM.FrameSkip;6" "kp_60;SlimSLAM.KpMax;60" "mode_1;SlimSLAM.ProcMode;1"
    )

    for test_case in "${TESTS[@]}"; do
        IFS=';' read -r TEST_NAME YAML_KEY YAML_VALUE <<< "$test_case"
        
        TEST_DIR="$SEQUENCE_RESULTS_DIR/$TEST_NAME"
        mkdir -p $TEST_DIR

        # We create the temp yaml file in the root directory for simplicity
        TEMP_YAML_FILE="./temp_settings_for_run.yaml"
        
        run_command cp "$BASE_TRAINING_SETTINGS_FILE" "$TEMP_YAML_FILE"
        
        if [ "$TEST_NAME" == "default" ]; then
            echo -e "\n[CONFIGURING] Test: $TEST_NAME (using baseline settings)..."
        else
            echo -e "\n[CONFIGURING] Test: $TEST_NAME. Setting $YAML_KEY to $YAML_VALUE..."
            run_command sed -i "s|^\($YAML_KEY:\s*\).*|\1$YAML_VALUE|" "$TEMP_YAML_FILE"
            if [ "$YAML_KEY" == "SlimSLAM.KpMax" ]; then
                run_command sed -i "s|^\(SlimSLAM.KpMin:\s*\).*|\154|" "$TEMP_YAML_FILE"
            fi
        fi
        
        echo "[RUNNING] Test: $TEST_NAME..."
        run_command "$EXEC_FILE" "$VOC_FILE" "$TEMP_YAML_FILE" "$SEQUENCE_PATH" "$TIMESTAMPS_FILE"

        echo "  -> Moving execution artifacts to $TEST_DIR..."
        
        # This is the primary trajectory file used for analysis. Rename it for clarity.
        if [ -f "CameraTrajectory.txt" ]; then
            run_command mv "CameraTrajectory.txt" "$TEST_DIR/trajectory.txt"
        fi
        # List of other expected artifacts to move.
        ARTIFACTS=(
            "ExecMean.txt" "KeyFrameTrajectory.txt" "LBA_Stats.txt"
            "LocalMapTimeStats.txt" "SessionInfo.txt" "TrackingTimeStats.txt" "$TEMP_YAML_FILE"
        )
        for artifact in "${ARTIFACTS[@]}"; do
            # Check if the file exists before moving, to prevent errors on failed runs
            if [ -f "$artifact" ]; then
                run_command mv "$artifact" "$TEST_DIR/"
            fi
        done
    done

    # --- Final Step: Generate the Control File for this Sequence ---
    echo -e "\n[ANALYZING] Generating SlimSLAM Control File for $SEQUENCE_NAME..."
    GROUND_TRUTH_PATH="${SEQUENCE_PATH}/mav0/state_groundtruth_estimate0/data.csv"
    CONTROL_FILE_OUT="${CONTROL_FILES_BASE_DIR}/slamslim_controls_${SEQUENCE_NAME}.txt"
    
    if [ ! -f "$GROUND_TRUTH_PATH" ]; then
        echo "ERROR: Ground truth file not found for $SEQUENCE_NAME. Skipping control file generation."
        continue
    fi
    run_command python3 "$PYTHON_GENERATOR_SCRIPT" "$SEQUENCE_PATH" "$TIMESTAMPS_FILE" "$GROUND_TRUTH_PATH" "$SEQUENCE_RESULTS_DIR" "$CONTROL_FILE_OUT" "$SEQUENCE_NAME"
    echo "-------------------------------------------------"
done

echo "================================================="
if [ "$DRY_RUN" = true ]; then
    echo "Dry run complete."
else
    echo "All sequences processed."
fi
echo "================================================="