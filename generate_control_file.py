import numpy as np
import os
import re
import sys

def load_tum_trajectory(filepath):
    """
    Loads a trajectory file in TUM format (timestamp tx ty tz qx qy qz qw).
    Returns a dictionary mapping {timestamp: [tx, ty, tz, qx, qy, qz, qw]}.
    """
    try:
        data = np.loadtxt(filepath, delimiter=' ', dtype=np.float64)
        if data.ndim == 1: # Handle files with a single line
            data = data.reshape(1, -1)
        return {row[0]: row[1:8] for row in data}
    except Exception as e:
        print(f"Warning: Could not load or parse {filepath}. Reason: {e}")
        return {}

def pose_translation_error(pose_gt, pose_est):
    """Calculates the absolute translational error between two poses."""
    return np.linalg.norm(pose_gt[0:3] - pose_est[0:3])

def parse_config_from_filename(filename, sequence_name_in_file):
    """
    Parses a single knob and value from a filename, specific to a sequence.
    Example: MH_01_easy_skip_2.txt -> {'key': 'skip', 'value': 2}
    """
    pattern = re.compile(rf"{re.escape(sequence_name_in_file)}_([a-zA-Z]+)_(\d+)\.txt")
    match = pattern.search(filename)
    if match:
        return {'key': match.group(1), 'value': int(match.group(2))}
    return None

def main(sequence_path_arg, timestamps_file_arg, ground_truth_path_arg, results_dir_arg, control_file_out_arg, dataset_name_arg):
    # --- Configuration from arguments ---
    GROUND_TRUTH_PATH = ground_truth_path_arg
    RESULTS_DIR = results_dir_arg # This is specific to the current sequence, e.g., ./results_base/MH_01_easy
    CONTROL_FILE_OUT = control_file_out_arg
    DATASET_NAME = dataset_name_arg # This is the sequence name like MH_01_easy

    # --- Load Ground Truth ---
    print(f"Processing for dataset: {DATASET_NAME}")
    print(f"Loading ground truth from: {GROUND_TRUTH_PATH}")
    try:
        gt_raw = np.loadtxt(GROUND_TRUTH_PATH, delimiter=',', skiprows=1)
        # EuRoC GT: timestamp, p_x, p_y, p_z, q_w, q_x, q_y, q_z, ...
        # Convert to TUM format pose: tx,ty,tz, qx,qy,qz,qw
        gt_poses = {
            row[0] * 1e-9: np.array([row[1], row[2], row[3], row[5], row[6], row[7], row[4]])
            for row in gt_raw
        }
        print(f"Loaded {len(gt_poses)} ground truth poses.")
    except Exception as e:
        print(f"FATAL: Could not load ground truth {GROUND_TRUTH_PATH}: {e}")
        return

    # --- Load all trajectory results for the current sequence ---
    print(f"Loading results from {RESULTS_DIR} for sequence {DATASET_NAME}...")
    
    baseline_filename = f"{DATASET_NAME}_default_0.txt"
    baseline_file_path = os.path.join(RESULTS_DIR, baseline_filename)
    baseline_traj = load_tum_trajectory(baseline_file_path)
    if not baseline_traj:
        print(f"FATAL: Baseline trajectory {baseline_file_path} not found or empty. Skipping generation for {DATASET_NAME}.")
        return
    
    alt_trajectories = {}
    for filename in os.listdir(RESULTS_DIR):
        if filename == baseline_filename: continue # Skip baseline file itself
        config = parse_config_from_filename(filename, DATASET_NAME)
        if config:
            alt_trajectories[(config['key'], config['value'])] = load_tum_trajectory(os.path.join(RESULTS_DIR, filename))
    
    print(f"Loaded baseline and {len(alt_trajectories)} alternative trajectories for {DATASET_NAME}.")

    # --- Find the best op for each timestamp ---
    print(f"Comparing trajectories to baseline for {DATASET_NAME}...")
    best_ops_for_timestamps = {} # {timestamp: {'key': key, 'value': value, 'error': error}}
    
    for ts_gt, pose_gt in gt_poses.items():
        # Find error for the baseline run at this timestamp
        baseline_timestamps = np.array(list(baseline_traj.keys()))
        closest_ts_base_idx = np.argmin(np.abs(baseline_timestamps - ts_gt))
        closest_ts_base = baseline_timestamps[closest_ts_base_idx]
        
        if abs(closest_ts_base - ts_gt) > 0.02: continue # Timestamp mismatch too large
        
        current_min_error = pose_translation_error(pose_gt, baseline_traj[closest_ts_base])
        # Default to baseline (no specific SlimSLAM command needed for this timestamp)
        winning_op_details = {'key': 'default', 'value': 0, 'error': current_min_error} 

        # Check if any alternative run is better
        for config_tuple, traj_data in alt_trajectories.items():
            if not traj_data: continue # Skip if trajectory failed to load
            
            alt_traj_timestamps = np.array(list(traj_data.keys()))
            closest_ts_alt_idx = np.argmin(np.abs(alt_traj_timestamps - ts_gt))
            closest_ts_alt = alt_traj_timestamps[closest_ts_alt_idx]

            if abs(closest_ts_alt - ts_gt) < 0.02: # Timestamp match
                error = pose_translation_error(pose_gt, traj_data[closest_ts_alt])
                if error < current_min_error:
                    current_min_error = error
                    winning_op_details = {'key': config_tuple[0], 'value': config_tuple[1], 'error': current_min_error}
        
        best_ops_for_timestamps[ts_gt] = winning_op_details

    # --- Write the final control file with stateful logic ---
    os.makedirs(os.path.dirname(CONTROL_FILE_OUT), exist_ok=True) # Ensure directory exists
    with open(CONTROL_FILE_OUT, 'w') as f:
        print(f"Generating stateful control commands and writing to {CONTROL_FILE_OUT}...")

        # Define the full default/baseline state
        default_config_state = {
            'Skip_Frames': 0,
            'KP_max': 200,
            'KP_min': 180,
            'Processing_Frames': 2 # 2=Stereo
        }

        # Track the last configuration that was written to the file
        last_written_config_state = default_config_state.copy()
        commands_written = 0

        # Iterate through timestamps and write commands only when the best state changes
        for ts, op_details in sorted(best_ops_for_timestamps.items()):
            # Determine the full target state for this timestamp
            target_config_state = default_config_state.copy()
            
            key, value = op_details['key'], op_details['value']
            if key == "skip":
                target_config_state['Skip_Frames'] = value
            elif key == "kp":
                target_config_state['KP_max'] = value
                target_config_state['KP_min'] = 54 if value == 60 else 180
            elif key == "mode":
                target_config_state['Processing_Frames'] = value

            # Compare target state with the last written state and write commands for differences
            if target_config_state != last_written_config_state:
                # Iterate through each knob and write a command if its value has changed
                for knob_name, target_value in target_config_state.items():
                    if target_value != last_written_config_state.get(knob_name):
                        f.write(f"{DATASET_NAME},{ts:.9f},{knob_name},{target_value}\n")
                        commands_written += 1
                
                # Update the last written state to this new target state
                last_written_config_state = target_config_state.copy()
                
        print(f"Wrote {commands_written} state-change commands.")

    print(f"Control file generation for {DATASET_NAME} complete: {CONTROL_FILE_OUT}")

if __name__ == "__main__":
    if len(sys.argv) != 7:
        print("Usage: python generate_control_file.py <sequence_path> <timestamps_file_path> <ground_truth_path> <results_dir_for_sequence> <control_file_output_path> <dataset_name>")
        print("Example: python generate_control_file.py /data/MH_01_easy /app/ts.txt /data/gt.csv /app/results/MH_01_easy /app/ctrl/MH_01.txt MH_01_easy")
        sys.exit(1)
    
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])