#!/bin/bash

# ORBSLAM3 Benchmarking Script
# This script performs benchmarking on the MH01 video dataset while collecting system-level and internal metrics of ORBSLAM3.

# Get the current date for creating unique result directories and log files
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

# Function to execute ORBSLAM3 and save results
run_orbslam() {
  local config_file=$1
  local result_folder_prefix=$2
  local run_number=$3
  local log_file="cout_${result_folder_prefix}_${run_number}_${DATE}.log"

  echo "Starting ORBSLAM3 run #${run_number} with configuration: $config_file"
  ./Examples/Stereo-Inertial/stereo_inertial_euroc ./Vocabulary/ORBvoc.txt $config_file ./Datasets/EuRoc/MH_01_easy ./Examples/Stereo-Inertial/EuRoC_TimeStamps/MH01.txt dataset-MH01_stereo_imu 2>&1 | tee $log_file

  echo "Saving results..."
  local result_folder="${result_folder_prefix}_${DATE}_run_${run_number}"
  mkdir -p $result_folder
  mv LocalMapTimeStats.txt ExecMean.txt f_dataset-MH01_stereo_imu.txt SessionInfo.txt kf_dataset-MH01_stereo_imu.txt LBA_Stats.txt TrackingTimeStats.txt $log_file $result_folder

  # Move map_points.csv if it exists
  if [ -f map_points.csv ]; then
    mv map_points.csv $result_folder
  fi

  echo "Results saved in $result_folder"
}

# Number of runs for each configuration
NUM_RUNS=100

# Deadline Run
for ((i=1; i<=NUM_RUNS; i++)); do
  run_orbslam ./Examples/Stereo-Inertial/EuRoC_deadlines.yaml "result_mh01_stereo_inertial_deadlines" $i
done

# Deadline + FOV Run
for ((i=1; i<=NUM_RUNS; i++)); do
  run_orbslam ./Examples/Stereo-Inertial/EuRoC_fov_deadlines.yaml "result_mh01_stereo_inertial_fov_deadlines" $i
done

# Field of View (FOV) Run
for ((i=1; i<=NUM_RUNS; i++)); do
  run_orbslam ./Examples/Stereo-Inertial/EuRoC_fov.yaml "result_mh01_stereo_inertial_fov" $i
done

# Normal Run
for ((i=1; i<=NUM_RUNS; i++)); do
  run_orbslam ./Examples/Stereo-Inertial/EuRoC.yaml "result_mh01_stereo_inertial_normal" $i
done

