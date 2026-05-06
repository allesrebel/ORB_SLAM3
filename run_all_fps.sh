#!/bin/bash

# Define the target FPS values to test
FPS_VALUES=(2 5 10 15 20)

# (Optional) allow overriding dataset for quick verification
# If a dataset is provided as arg 1, we will modify run_fps_eval.sh temporarily.
# For full runs, this is not needed since DATASETS array in run_fps_eval.sh contains all 11.
if [ ! -z "$1" ]; then
    echo "Temporarily overriding datasets to: $1"
    # Create a backup
    cp run_fps_eval.sh run_fps_eval.sh.bak
    sed -i "s/^DATASETS=(.*)/DATASETS=($1)/" run_fps_eval.sh
fi

for fps in "${FPS_VALUES[@]}"; do
    echo "=================================================="
    echo "Starting test run for Target FPS: $fps"
    echo "=================================================="
    ./run_fps_eval.sh $fps
done

if [ ! -z "$1" ]; then
    # Restore backup
    mv run_fps_eval.sh.bak run_fps_eval.sh
    echo "Restored original dataset list."
fi

echo "All test runs completed. Running aggregation script..."
python3 plot_error_vs_fps.py
