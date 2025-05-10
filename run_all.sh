#!/bin/bash

# Get the current date for creating unique result directories and log files
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

# Function to execute ORBSLAM3 and save results
run_orbslam() {
  local config_file=$1          # YAML config
  local result_folder_prefix=$2 # “result_stereo_inertial_* …”
  local dataset=$3              # MH01 … V203
  local run_number=$4
  local mask_size=$5
  local log_file="cout_${result_folder_prefix}_${dataset}_${mask_size}_${run_number}_${DATE}.log"

  # -------------------------------------------------------------------------
  # Convert dataset code (MH01, V202 …) to folder name (MH_01, V2_02 …)
  # -------------------------------------------------------------------------
  local dataset_with_underscore
  if [[ $dataset == MH* ]]; then          # MH01 → MH_01
    dataset_with_underscore="${dataset:0:2}_${dataset:2:2}"
  elif [[ $dataset == V* ]]; then         # V202 → V2_02,  V101 → V1_01 …
    dataset_with_underscore="V${dataset:1:1}_${dataset:2:2}"
  else                                    # any other pattern (future-proof)
    dataset_with_underscore="$dataset"
  fi
  # -------------------------------------------------------------------------

  local command="./Examples/Stereo-Inertial/stereo_inertial_euroc \
./Vocabulary/ORBvoc.txt $config_file \
./Datasets/EuRoc/${dataset_with_underscore}* \
./Examples/Stereo-Inertial/EuRoC_TimeStamps/${dataset}.txt \
dataset-${dataset}_stereo_imu"

  echo "Running command: $command"
  $command > "$log_file"

  echo "Saving results..."
  local result_folder="${DATE}_${result_folder_prefix}_${dataset}_${mask_size}_run_${run_number}"
  mkdir -p "$result_folder"
  mv LocalMapTimeStats.txt ExecMean.txt LBA_Stats.txt TrackingTimeStats.txt SessionInfo.txt "$log_file" "$result_folder" 2>/dev/null

  # Move optional outputs if present
  for file in map_points.csv "f_dataset-${dataset}_stereo_imu.txt" \
              "kf_dataset-${dataset}_stereo_imu.txt" "cellManager.txt"; do
    [[ -f $file ]] && mv "$file" "$result_folder"
  done
  echo "Results saved in $result_folder"
}

# Number of runs for each configuration
NUM_RUNS=10

# Datasets to process
DATASETS=("MH01" "MH02" "MH03" "MH04" "MH05" "V101" "V102" "V103" "V201" "V202" "V203")

# Configurations to process
CONFIGURATIONS=(
  "./Examples/Stereo-Inertial/EuRoC_oasis.yaml result_stereo_inertial_oasis"
  "./Examples/Stereo-Inertial/EuRoC_deadlines.yaml result_stereo_inertial_deadlines"
  "./Examples/Stereo-Inertial/EuRoC_fov_deadlines.yaml result_stereo_inertial_fov_deadlines"
  "./Examples/Stereo-Inertial/EuRoC_fov.yaml result_stereo_inertial_fov"
  "./Examples/Stereo-Inertial/EuRoC.yaml result_stereo_inertial_normal"
)

# Array to store all the commands
commands=()

for config_pair in "${CONFIGURATIONS[@]}"; do
  IFS=' ' read -r BASE_CONFIG RESULT_FOLDER_PREFIX <<< "$config_pair"

  if [[ $BASE_CONFIG == *"fov"* ]]; then
    # Extract the base name of the config file without extension
    FILENAME=$(basename "$BASE_CONFIG" .yaml)

    # Loop through different mask sizes and create corresponding configurations
    for ((mask_size=2; mask_size<=12; mask_size++)); do
      CONFIG_FILE="${FILENAME}_mask_${mask_size}x${mask_size}.yaml"
      if [ ! -f "$CONFIG_FILE" ]; then
        cp "$BASE_CONFIG" "$CONFIG_FILE"
        # Update or add System.maskHeight
        if ! grep -q "^System.maskHeight:" "$CONFIG_FILE"; then
          echo "System.maskHeight: ${mask_size}" >> "$CONFIG_FILE"
        else
          sed -i "s/^System.maskHeight: [0-9]*/System.maskHeight: ${mask_size}/" "$CONFIG_FILE"
        fi
        # Update or add System.maskWidth
        if ! grep -q "^System.maskWidth:" "$CONFIG_FILE"; then
          echo "System.maskWidth: ${mask_size}" >> "$CONFIG_FILE"
        else
          sed -i "s/^System.maskWidth: [0-9]*/System.maskWidth: ${mask_size}/" "$CONFIG_FILE"
        fi
      fi

      # Collect all run commands for this configuration
      for ((i=1; i<=NUM_RUNS; i++)); do
        for dataset in "${DATASETS[@]}"; do
          commands+=("run_orbslam $CONFIG_FILE $RESULT_FOLDER_PREFIX $dataset $i $mask_size")
        done
      done
    done
  else
    # For non-FOV configurations, set mask_size to 0
    mask_size=0
    for ((i=1; i<=NUM_RUNS; i++)); do
      for dataset in "${DATASETS[@]}"; do
        commands+=("run_orbslam $BASE_CONFIG $RESULT_FOLDER_PREFIX $dataset $i $mask_size")
      done
    done
  fi
done

# Shuffle the full list of commands
shuffled_commands=$(printf "%s\n" "${commands[@]}" | shuf)

# Execute each command from the shuffled list
while IFS= read -r cmd; do
  echo "Executing: $cmd"
  eval "$cmd"
done <<< "$shuffled_commands"
