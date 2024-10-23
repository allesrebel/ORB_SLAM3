#!/bin/bash

# This script starts timing the MH01 easy
# video file, while collecting stats of
# system level metrics and internal metrics
# of ORBSLAM3

# finally do the actual orbslam with sample video
# NORMAL RUN
./Examples/Stereo-Inertial/stereo_inertial_euroc ./Vocabulary/ORBvoc.txt ./Examples/Stereo-Inertial/EuRoC.yaml ~/Datasets/EuRoc/MH01 ./Examples/Stereo-Inertial/EuRoC_TimeStamps/MH01.txt dataset-MH01_stereo_imu 2>&1 | tee mh01_stereo_inertial_cout.log

# save results into results folder
echo 'saving results now'
mkdir -p result_mh01_stereo_inertial_normal
mv LocalMapTimeStats.txt ExecMean.txt f_dataset-MH01_stereo_imu.txt SessionInfo.txt kf_dataset-MH01_stereo_imu.txt LBA_Stats.txt TrackingTimeStats.txt mh01_stereo_inertial_cout.log result_mh01_stereo_inertial_normal

echo 'saved in result_mh01_stereo_inertial_normal'

# FOV RUN
./Examples/Stereo-Inertial/stereo_inertial_euroc ./Vocabulary/ORBvoc.txt ./Examples/Stereo-Inertial/EuRoC_fov.yaml ~/Datasets/EuRoc/MH01 ./Examples/Stereo-Inertial/EuRoC_TimeStamps/MH01.txt dataset-MH01_stereo_imu 2>&1 | tee mh01_stereo_inertial_cout.log

# save results into results folder
echo 'saving results now'
mkdir -p result_mh01_stereo_inertial_fov
mv LocalMapTimeStats.txt ExecMean.txt f_dataset-MH01_stereo_imu.txt SessionInfo.txt kf_dataset-MH01_stereo_imu.txt LBA_Stats.txt TrackingTimeStats.txt mh01_stereo_inertial_cout.log result_mh01_stereo_inertial_fov

echo 'saved in result_mh01_stereo_inertial_fov!'

# DEAD LINE RUN
./Examples/Stereo-Inertial/stereo_inertial_euroc ./Vocabulary/ORBvoc.txt ./Examples/Stereo-Inertial/EuRoC_deadlines.yaml ~/Datasets/EuRoc/MH01 ./Examples/Stereo-Inertial/EuRoC_TimeStamps/MH01.txt dataset-MH01_stereo_imu 2>&1 | tee mh01_stereo_inertial_cout.log

# save results into results folder
echo 'saving results now'
mkdir -p result_mh01_stereo_inertial_deadlines
mv LocalMapTimeStats.txt ExecMean.txt f_dataset-MH01_stereo_imu.txt SessionInfo.txt kf_dataset-MH01_stereo_imu.txt LBA_Stats.txt TrackingTimeStats.txt mh01_stereo_inertial_cout.log result_mh01_stereo_inertial_deadlines

echo 'saved in result_mh01_stereo_inertial_deadlines!'

# DEAD LINE + FOV RUN
./Examples/Stereo-Inertial/stereo_inertial_euroc ./Vocabulary/ORBvoc.txt ./Examples/Stereo-Inertial/EuRoC_fov_deadlines.yaml ~/Datasets/EuRoc/MH01 ./Examples/Stereo-Inertial/EuRoC_TimeStamps/MH01.txt dataset-MH01_stereo_imu 2>&1 | tee mh01_stereo_inertial_cout.log

# save results into results folder
echo 'saving results now'
mkdir -p result_mh01_stereo_inertial_fov_deadlines
mv LocalMapTimeStats.txt ExecMean.txt f_dataset-MH01_stereo_imu.txt SessionInfo.txt kf_dataset-MH01_stereo_imu.txt LBA_Stats.txt TrackingTimeStats.txt mh01_stereo_inertial_cout.log result_mh01_stereo_inertial_fov_deadlines

echo 'saved in result_mh01_stereo_inertial_fov_deadlines!'
