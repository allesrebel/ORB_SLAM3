#!/bin/bash

# --- Configuration ---
VOC_FILE="./Vocabulary/ORBvoc.txt"
# IMPORTANT: Use a settings file configured for TRAINING mode
TRAINING_SETTINGS_FILE="./Examples/Stereo-Inertial/EuRoC_SlimSLAM_Training.yaml" # Assumes you created this
RESULTS_BASE_DIR="./slamslim_training_results" # Base directory for all sequence results
CONTROL_FILES_BASE_DIR="./slamslim_control_files" # Where Python script will output control files

EXEC_FILE="./Examples/Stereo-Inertial/stereo_inertial_euroc"
PYTHON_GENERATOR_SCRIPT="./generate_control_file.py" # Path to your Python script

# Define EuRoC sequences and their timestamp files
# Format: "SEQUENCE_PATH;TIMESTAMPS_FILE_PATH"
SEQUENCES=(
    "/path/to/your/euroc/datasets/MH_01_easy;/path/to/ORB_SLAM3/Examples/Stereo-Inertial/EuRoC_TimeStamps/MH01.txt"
    "/path/to/your/euroc/datasets/MH_02_easy;/path/to/ORB_SLAM3/Examples/Stereo-Inertial/EuRoC_TimeStamps/MH02.txt"
    "/path/to/your/euroc/datasets/V1_01_easy;/path/to/ORB_SLAM3/Examples/Stereo-Inertial/EuRoC_TimeStamps/V101.txt"
)

# --- Script Start ---
mkdir -p $RESULTS_BASE_DIR
mkdir -p $CONTROL_FILES_BASE_DIR

for seq_info in "${SEQUENCES[@]}"; do
    IFS=';' read -r SEQUENCE_PATH TIMESTAMPS_FILE <<< "$seq_info"
    
    SEQUENCE_NAME=$(basename $SEQUENCE_PATH)
    CURRENT_RESULTS_DIR="$RESULTS_BASE_DIR/$SEQUENCE_NAME"
    mkdir -p $CURRENT_RESULTS_DIR

    echo "================================================="
    echo "Processing Sequence: $SEQUENCE_NAME"
    echo "Results Dir: $CURRENT_RESULTS_DIR"
    echo "Training Settings: $TRAINING_SETTINGS_FILE"
    echo "================================================="

    # --- Run 1: The Default/Baseline Configuration ---
    echo -e "\nRunning BASELINE for $SEQUENCE_NAME..."
    $EXEC_FILE $VOC_FILE $TRAINING_SETTINGS_FILE $SEQUENCE_PATH $TIMESTAMPS_FILE default 0
    mv ./${SEQUENCE_NAME}_default_0.txt $CURRENT_RESULTS_DIR/

    # --- Run 2: Test Frame Skipping ---
    echo -e "\n--- Testing Frame Skip Values for $SEQUENCE_NAME ---"
    for skip in 1 2 3 4 5 6; do
        echo "Testing SKIP = $skip"
        $EXEC_FILE $VOC_FILE $TRAINING_SETTINGS_FILE $SEQUENCE_PATH $TIMESTAMPS_FILE skip $skip
        mv ./${SEQUENCE_NAME}_skip_${skip}.txt $CURRENT_RESULTS_DIR/
    done

    # --- Run 3: Test KeyPoint Limits ---
    echo -e "\n--- Testing KeyPoint (KP) Values for $SEQUENCE_NAME ---"
    echo "Testing KP_max = 60" # Only non-default
    $EXEC_FILE $VOC_FILE $TRAINING_SETTINGS_FILE $SEQUENCE_PATH $TIMESTAMPS_FILE kp 60
    mv ./${SEQUENCE_NAME}_kp_60.txt $CURRENT_RESULTS_DIR/

    # --- Run 4: Test Monocular Mode ---
    echo -e "\n--- Testing Processing Mode for $SEQUENCE_NAME ---"
    echo "Testing MODE = 1 (Mono)"
    $EXEC_FILE $VOC_FILE $TRAINING_SETTINGS_FILE $SEQUENCE_PATH $TIMESTAMPS_FILE mode 1
    mv ./${SEQUENCE_NAME}_mode_1.txt $CURRENT_RESULTS_DIR/
    
    # --- Generate Control File for this sequence ---
    echo -e "\n--- Generating SlimSLAM Control File for $SEQUENCE_NAME ---"
    python3 $PYTHON_GENERATOR_SCRIPT $SEQUENCE_PATH $TIMESTAMPS_FILE "$GROUND_TRUTH_BASE_PATH/$SEQUENCE_NAME/mav0/state_groundtruth_estimate0/data.csv" $CURRENT_RESULTS_DIR "$CONTROL_FILES_BASE_DIR/slamslim_controls_${SEQUENCE_NAME}.txt" $SEQUENCE_NAME
    # Note: GROUND_TRUTH_BASE_PATH needs to be defined or passed correctly.
    # The Python script will need to be updated to take these arguments.

done

echo "================================================="
echo "All sequences processed."
echo "Training results in: $RESULTS_BASE_DIR"
echo "Control files in: $CONTROL_FILES_BASE_DIR"
echo "================================================="