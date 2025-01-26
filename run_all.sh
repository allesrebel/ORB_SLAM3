#!/bin/bash

# Get the current date for creating unique result directories and log files
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

# Function to execute ORBSLAM3 and save results
run_orbslam() {
  local config_file=$1
  local result_folder_prefix=$2
  local dataset=$3
  local run_number=$4
  local mask_size=$5
  local log_file="cout_${result_folder_prefix}_${dataset}_${mask_size}_${run_number}_${DATE}.log"

  local dataset_with_underscore=$(echo $dataset | sed 's/\([A-Z]*\)\([0-9]*\)/\1_\2/')
  local command="./Examples/Stereo-Inertial/stereo_inertial_euroc ./Vocabulary/ORBvoc.txt $config_file ./Datasets/EuRoc/${dataset_with_underscore}* ./Examples/Stereo-Inertial/EuRoC_TimeStamps/${dataset}.txt dataset-${dataset}_stereo_imu"
  echo "Running command: $command"
  $command > $log_file

  echo "Saving results..."
  local result_folder="${DATE}_${result_folder_prefix}_${dataset}_${mask_size}_run_${run_number}"
  mkdir -p $result_folder
  mv LocalMapTimeStats.txt ExecMean.txt LBA_Stats.txt TrackingTimeStats.txt SessionInfo.txt $log_file $result_folder

  # Move additional output files if they exist
  for file in map_points.csv "f_dataset-${dataset}_stereo_imu.txt" "kf_dataset-${dataset}_stereo_imu.txt"; do
    if [ -f "$file" ]; then
      mv "$file" "$result_folder"
    fi
  done

  echo "Results saved in $result_folder"
}

# Number of runs for each configuration
NUM_RUNS=50

# Datasets to process
DATASETS=("MH01" "MH02" "MH03" "MH04" "MH05")

# Configurations to process
CONFIGURATIONS=(
  "./Examples/Stereo-Inertial/EuRoC_deadlines.yaml result_stereo_inertial_deadlines"
  "./Examples/Stereo-Inertial/EuRoC_fov_deadlines.yaml result_stereo_inertial_fov_deadlines"
  "./Examples/Stereo-Inertial/EuRoC_fov.yaml result_stereo_inertial_fov"
  "./Examples/Stereo-Inertial/EuRoC.yaml result_stereo_inertial_normal"
)

# Loop through configurations
for config_pair in "${CONFIGURATIONS[@]}"; do
  IFS=' ' read -r BASE_CONFIG RESULT_FOLDER_PREFIX <<< "$config_pair"

  # Check if config name contains "fov" or "FOV"
  if [[ $BASE_CONFIG == *"fov"* ]]; then
    # Extract the base name of the config file without extension
    FILENAME=$(basename "$BASE_CONFIG" .yaml)

    # Loop through different mask sizes and create corresponding configurations
    for ((mask_size=2; mask_size<=12; mask_size++)); do
      CONFIG_FILE="${FILENAME}_mask_${mask_size}x${mask_size}.yaml"
      if [ ! -f "$CONFIG_FILE" ]; then
        cp $BASE_CONFIG $CONFIG_FILE

        # Check if the config file has the lines, if not add them, else do the sed
        if ! grep -q "^System.maskHeight:" $CONFIG_FILE; then
          echo "System.maskHeight: ${mask_size}" >> $CONFIG_FILE
        else
          sed -i "s/^System.maskHeight: [0-9]*/System.maskHeight: ${mask_size}/" $CONFIG_FILE
        fi

        if ! grep -q "^System.maskWidth:" $CONFIG_FILE; then
          echo "System.maskWidth: ${mask_size}" >> $CONFIG_FILE
        else
          sed -i "s/^System.maskWidth: [0-9]*/System.maskWidth: ${mask_size}/" $CONFIG_FILE
        fi
      fi

      # Randomize dataset and configuration selection
      for ((i=1; i<=NUM_RUNS; i++)); do
        for dataset in "${DATASETS[@]}"; do
          run_orbslam $CONFIG_FILE $RESULT_FOLDER_PREFIX $dataset $i $mask_size
        done | shuf
      done | shuf
    done
  else
    # If not FOV-related, just run the base configuration as is
    # with mask_size set to something like 0 to indicate no mask
    mask_size=0
    for ((i=1; i<=NUM_RUNS; i++)); do
      for dataset in "${DATASETS[@]}"; do
        run_orbslam $BASE_CONFIG $RESULT_FOLDER_PREFIX $dataset $i $mask_size
      done
    done
  fi

done

