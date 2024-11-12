#!/bin/bash

# ORBSLAM3 Benchmarking Script
# This script performs benchmarking on the MH01 - MH05 video datasets while collecting system-level and internal metrics of ORBSLAM3.

# Get the current date for creating unique result directories and log files
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

# Function to execute ORBSLAM3 and save results
run_orbslam() {
  local config_file=$1
  local result_folder_prefix=$2
  local dataset=$3
  local run_number=$4
  local log_file="cout_${result_folder_prefix}_${dataset}_${run_number}_${DATE}.log"

  echo "Starting ORBSLAM3 run #${run_number} on dataset ${dataset} with configuration: $config_file"
  local dataset_with_underscore=$(echo $dataset | sed 's/\([A-Z]*\)\([0-9]*\)/\1_\2/')
  local command="./Examples/Stereo-Inertial/stereo_inertial_euroc ./Vocabulary/ORBvoc.txt $config_file ./Datasets/EuRoc/${dataset_with_underscore}* ./Examples/Stereo-Inertial/EuRoC_TimeStamps/${dataset}.txt dataset-${dataset}_stereo_imu"
  echo "Running command: $command"
  $command 2>&1 | tee $log_file

  echo "Saving results..."
  local result_folder="${result_folder_prefix}_${dataset}_${DATE}_run_${run_number}"
  mkdir -p $result_folder
  mv LocalMapTimeStats.txt ExecMean.txt f_dataset-${dataset}_stereo_imu.txt SessionInfo.txt kf_dataset-${dataset}_stereo_imu.txt LBA_Stats.txt TrackingTimeStats.txt $log_file $result_folder

  # Move map_points.csv if it exists
  if [ -f map_points.csv ]; then
    mv map_points.csv $result_folder
  fi

  echo "Results saved in $result_folder"
}

# Number of runs for each configuration
NUM_RUNS=1

# Datasets to process
DATASETS=("MH01" "MH02" "MH03" "MH04" "MH05")

# Configurations to process
CONFIGURATIONS=(
  "./Examples/Stereo-Inertial/EuRoC_deadlines.yaml result_stereo_inertial_deadlines"
  "./Examples/Stereo-Inertial/EuRoC_fov_deadlines.yaml result_stereo_inertial_fov_deadlines"
  "./Examples/Stereo-Inertial/EuRoC_fov.yaml result_stereo_inertial_fov"
  "./Examples/Stereo-Inertial/EuRoC.yaml result_stereo_inertial_normal"
)

# Randomize dataset and configuration selection
for ((i=1; i<=NUM_RUNS; i++)); do
  for dataset in "${DATASETS[@]}"; do
    for config in "${CONFIGURATIONS[@]}"; do
      config_file=$(echo $config | awk '{print $1}')
      result_folder_prefix=$(echo $config | awk '{print $2}')
      run_orbslam $config_file $result_folder_prefix $dataset $i
    done | shuf
  done | shuf
done
