#!/bin/bash

# Target FPS for the evaluation
TARGET_FPS=${1:-10}

# Get the current date for creating unique result directories and log files
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

# Function to execute ORBSLAM3, save results, and evaluate
run_orbslam() {
  local config_file=$1          # YAML config
  local result_folder_prefix=$2 # “result_stereo_inertial_* …”
  local dataset=$3              # MH01 … V203
  local run_number=$4
  local mask_size=$5
  local target_fps=$6
  local log_file="cout_${result_folder_prefix}_${dataset}_${mask_size}_fps_${target_fps}_${run_number}_${DATE}.log"

  # Convert dataset code (MH01, V202 …) to folder name (MH_01, V2_02 …)
  local dataset_with_underscore
  if [[ $dataset == MH* ]]; then
    dataset_with_underscore="${dataset:0:2}_${dataset:2:2}"
  elif [[ $dataset == V* ]]; then
    dataset_with_underscore="V${dataset:1:1}_${dataset:2:2}"
  else
    dataset_with_underscore="$dataset"
  fi

  local command="./Examples/Stereo-Inertial/stereo_inertial_euroc \
  ./Vocabulary/ORBvoc.txt $config_file \
  ./Datasets/EuRoc/${dataset_with_underscore}* \
  ./Examples/Stereo-Inertial/EuRoC_TimeStamps/${dataset}.txt \
  dataset-${dataset}_stereo_imu"

  echo "Running command: $command"
  $command > "$log_file"

  echo "Evaluating results..."
  local result_folder="${DATE}_${result_folder_prefix}_${dataset}_${mask_size}_fps_${target_fps}_run_${run_number}"
  mkdir -p "$result_folder"
  
  # Run ATE evaluation
  local est_traj_file="f_dataset-${dataset}_stereo_imu.txt"
  local gt_traj_file="evaluation/Ground_truth/EuRoC_left_cam/${dataset}_GT.txt"
  if [[ -f "$est_traj_file" && -f "$gt_traj_file" ]]; then
    python3 evaluation/evaluate_ate_scale.py "$gt_traj_file" "$est_traj_file" --scale 1.0 > "${result_folder}/ate_evaluation.txt"
    if [[ -f "trajectory_pair.csv" ]]; then
      python3 plot_trajectory.py "trajectory_pair.csv" -o "${result_folder}/trajectory_plot.png"
    fi
  else
    echo "Warning: Trajectory file(s) not found. Evaluation skipped." > "${result_folder}/ate_evaluation.txt"
  fi

  echo "Saving results..."
  mv LocalMapTimeStats.txt ExecMean.txt LBA_Stats.txt TrackingTimeStats.txt SessionInfo.txt "$log_file" "$result_folder" 2>/dev/null

  # Move optional outputs if present
  for file in map_points.csv "$est_traj_file" \
              "kf_dataset-${dataset}_stereo_imu.txt" "cellManager.txt" \
              "trajectory_pair.csv" "ground_truth_traj.csv" "estimated_traj_aligned.csv" "difference_segments.csv"; do
    [[ -f $file ]] && mv "$file" "$result_folder"
  done
  echo "Results saved in $result_folder"
}

# Number of runs for each configuration
NUM_RUNS=1

# Datasets to process
DATASETS=("MH01" "MH02" "MH03" "MH04" "MH05" "V101" "V102" "V103" "V201" "V202" "V203")

# Configurations to process
CONFIGURATIONS=(
  "./Examples/Stereo-Inertial/EuRoC.yaml result_stereo_inertial_normal"
)

# Array to store all the commands
commands=()

for config_pair in "${CONFIGURATIONS[@]}"; do
  IFS=' ' read -r BASE_CONFIG RESULT_FOLDER_PREFIX <<< "$config_pair"

  # Create a copy of the config file with the target FPS
  FILENAME=$(basename "$BASE_CONFIG" .yaml)
  CONFIG_FILE="./Examples/Stereo-Inertial/${FILENAME}_fps_${TARGET_FPS}.yaml"
  
  cp "$BASE_CONFIG" "$CONFIG_FILE"
  
  # Update or add System.TargetFPS
  if ! grep -q "^System.TargetFPS:" "$CONFIG_FILE"; then
    echo "System.TargetFPS: ${TARGET_FPS}" >> "$CONFIG_FILE"
  else
    sed -i "s/^System.TargetFPS: .*/System.TargetFPS: ${TARGET_FPS}/" "$CONFIG_FILE"
  fi

  mask_size=0
  for ((i=1; i<=NUM_RUNS; i++)); do
    for dataset in "${DATASETS[@]}"; do
      commands+=("run_orbslam $CONFIG_FILE $RESULT_FOLDER_PREFIX $dataset $i $mask_size $TARGET_FPS")
    done
  done
done

# Shuffle the full list of commands
shuffled_commands=$(printf "%s\n" "${commands[@]}" | shuf)

# Execute each command from the shuffled list
while IFS= read -r cmd; do
  echo "Executing: $cmd"
  eval "$cmd"
done <<< "$shuffled_commands"
