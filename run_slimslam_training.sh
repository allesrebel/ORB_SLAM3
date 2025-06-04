#!/bin/bash

# This script automates the process of generating data for the SlimSLAM controller.
# It iterates through all specified EuRoC sequences, runs ORB-SLAM3 with various
# configurations (one knob at a time), and then calls a Python script to analyze
# the resulting trajectories and generate an optimal control file for each sequence.
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
        # In dry run mode, just print the command that would be executed.
        echo "[DRY RUN] Would execute: $@"
    else
        # In normal mode, execute the command.
        # The "$@" expands to all arguments passed to this function.
        "$@"
    fi
}


# --- Configuration ---
# Set these paths to match your system environment.
ORB_SLAM3_BASE_PATH="${ORB_SLAM3_BASE_PATH:-.}"
EUROC_BASE_PATH="${EUROC_BASE_PATH:-./Datasets/EuRoc}" # Dir containing MH_01_easy, etc.

# --- Script Variables (should not need to change if paths above are correct) ---
VOC_FILE="${ORB_SLAM3_BASE_PATH}/Vocabulary/ORBvoc.txt"
TRAINING_SETTINGS_FILE="${ORB_SLAM3_BASE_PATH}/Examples/Stereo-Inertial/EuRoC_SlimSLAM_Training.yaml"

RESULTS_BASE_DIR="./slamslim_training_results" # Base directory for all sequence trajectory files
CONTROL_FILES_BASE_DIR="./slamslim_control_files" # Final output directory for control files

EXEC_FILE="${ORB_SLAM3_BASE_PATH}/Examples/Stereo-Inertial/stereo_inertial_euroc"
PYTHON_GENERATOR_SCRIPT="./generate_control_file.py" # Path to your Python script

# Define all 11 EuRoC sequences and their corresponding timestamp files.
# The timestamp file paths are relative to the ORB_SLAM3_BASE_PATH.
# The sequence paths are relative to the EUROC_BASE_PATH.
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
# Create base directories for results and final control files if they don't exist.
# These actions are safe to run even in dry-run mode.
mkdir -p $RESULTS_BASE_DIR
mkdir -p $CONTROL_FILES_BASE_DIR

# Check if the executable exists before starting the main loop.
if [ ! -f "$EXEC_FILE" ]; then
    echo "ERROR: SLAM Executable not found at $EXEC_FILE"
    echo "Please ensure ORB-SLAM3 is built and the path is correct."
    exit 1
fi

# Check if the Python generator script exists.
if [ ! -f "$PYTHON_GENERATOR_SCRIPT" ]; then
    echo "ERROR: Python generator script not found at $PYTHON_GENERATOR_SCRIPT"
    exit 1
fi

# Loop through each sequence defined in the SEQUENCES array.
for seq_info in "${SEQUENCES[@]}"; do
    # Parse the sequence name (e.g., "MH_01_easy") and its relative timestamp file path.
    IFS=';' read -r SEQUENCE_NAME REL_TIMESTAMPS_FILE <<< "$seq_info"
    
    # Construct the full paths for the sequence data and its timestamp file.
    SEQUENCE_PATH="${EUROC_BASE_PATH}/${SEQUENCE_NAME}"
    TIMESTAMPS_FILE="${ORB_SLAM3_BASE_PATH}/${REL_TIMESTAMPS_FILE}"

    # Check if the sequence directory exists.
    if [ ! -d "$SEQUENCE_PATH" ]; then
        echo "WARNING: Sequence directory not found for $SEQUENCE_NAME at $SEQUENCE_PATH. Skipping."
        continue
    fi
    # Check if the timestamps file exists.
    if [ ! -f "$TIMESTAMPS_FILE" ]; then
        echo "WARNING: Timestamps file not found for $SEQUENCE_NAME at $TIMESTAMPS_FILE. Skipping."
        continue
    fi

    # Define a dedicated directory for the current sequence's trajectory results.
    CURRENT_RESULTS_DIR="$RESULTS_BASE_DIR/$SEQUENCE_NAME"
    mkdir -p $CURRENT_RESULTS_DIR # Safe to run

    echo "================================================="
    echo "Processing Sequence: $SEQUENCE_NAME"
    echo "Dataset Path: $SEQUENCE_PATH"
    echo "Timestamps: $TIMESTAMPS_FILE"
    echo "Results will be saved in: $CURRENT_RESULTS_DIR"
    echo "================================================="

    # --- Test 1: The Default/Baseline Configuration ---
    echo -e "\n[RUNNING] BASELINE configuration for $SEQUENCE_NAME..."
    run_command $EXEC_FILE $VOC_FILE $TRAINING_SETTINGS_FILE $SEQUENCE_PATH $TIMESTAMPS_FILE default 0
    # Move the generated trajectory file into the sequence's result directory.
    # The executable saves files as ./<SEQUENCE_NAME>_<config_key>_<config_value>.txt
    run_command mv ./${SEQUENCE_NAME}_default_0.txt $CURRENT_RESULTS_DIR/

    # --- Test 2: Frame Skipping Configurations ---
    echo -e "\n[RUNNING] Frame Skip tests for $SEQUENCE_NAME..."
    for skip_val in 1 2 3 4 5 6; do
        echo "  -> Testing SKIP = $skip_val"
        run_command $EXEC_FILE $VOC_FILE $TRAINING_SETTINGS_FILE $SEQUENCE_PATH $TIMESTAMPS_FILE skip $skip_val
        run_command mv ./${SEQUENCE_NAME}_skip_${skip_val}.txt $CURRENT_RESULTS_DIR/
    done

    # --- Test 3: KeyPoint Limits Configuration ---
    echo -e "\n[RUNNING] KeyPoint (KP) limit test for $SEQUENCE_NAME..."
    # Only testing the alternative KP_max value of 60 (vs. default 200).
    echo "  -> Testing KP_max = 60"
    run_command $EXEC_FILE $VOC_FILE $TRAINING_SETTINGS_FILE $SEQUENCE_PATH $TIMESTAMPS_FILE kp 60
    run_command mv ./${SEQUENCE_NAME}_kp_60.txt $CURRENT_RESULTS_DIR/

    # --- Test 4: Monocular Mode Configuration ---
    echo -e "\n[RUNNING] Processing Mode test for $SEQUENCE_NAME..."
    # Testing mode 1 (Monocular) vs. default mode 2 (Stereo).
    echo "  -> Testing MODE = 1 (Monocular)"
    run_command $EXEC_FILE $VOC_FILE $TRAINING_SETTINGS_FILE $SEQUENCE_PATH $TIMESTAMPS_FILE mode 1
    run_command mv ./${SEQUENCE_NAME}_mode_1.txt $CURRENT_RESULTS_DIR/
    
    # --- Final Step: Generate the Control File for this Sequence ---
    echo -e "\n[ANALYZING] Generating SlimSLAM Control File for $SEQUENCE_NAME..."
    # Construct the path to the ground truth data for the current sequence.
    # This assumes the standard EuRoC ground truth file path relative to the sequence directory.
    GROUND_TRUTH_PATH="${SEQUENCE_PATH}/mav0/state_groundtruth_estimate0/data.csv"
    # Define the final output path for the control file.
    CONTROL_FILE_OUT="${CONTROL_FILES_BASE_DIR}/slamslim_controls_${SEQUENCE_NAME}.txt"
    
    # Check if the ground truth file exists before calling the python script.
    if [ ! -f "$GROUND_TRUTH_PATH" ]; then
        echo "ERROR: Ground truth file not found for $SEQUENCE_NAME at $GROUND_TRUTH_PATH"
        echo "Skipping control file generation for this sequence."
        continue # Skip to the next sequence in the main loop
    fi

    # Execute the Python script with all necessary paths and names.
    # Arguments for generate_control_file.py:
    # 1: sequence_path_arg       (e.g., /path/to/euroc/MH_01_easy)
    # 2: timestamps_file_arg     (e.g., /path/to/ORB_SLAM3/Examples/Stereo-Inertial/EuRoC_TimeStamps/MH01.txt)
    # 3: ground_truth_path_arg   (e.g., /path/to/euroc/MH_01_easy/mav0/state_groundtruth_estimate0/data.csv)
    # 4: results_dir_arg         (e.g., ./slamslim_training_results/MH_01_easy)
    # 5: control_file_out_arg    (e.g., ./slamslim_control_files/slamslim_controls_MH_01_easy.txt)
    # 6: dataset_name_arg        (e.g., MH_01_easy)
    run_command python3 $PYTHON_GENERATOR_SCRIPT "$SEQUENCE_PATH" "$TIMESTAMPS_FILE" "$GROUND_TRUTH_PATH" "$CURRENT_RESULTS_DIR" "$CONTROL_FILE_OUT" "$SEQUENCE_NAME"
    
    echo "-------------------------------------------------"
done

echo "================================================="
if [ "$DRY_RUN" = true ]; then
    echo "Dry run complete."
else
    echo "All sequences processed."
    echo "Training trajectory results are in: $RESULTS_BASE_DIR"
    echo "Final control files are in: $CONTROL_FILES_BASE_DIR"
    echo "Review any WARNINGS or ERRORS above."
fi
echo "================================================="