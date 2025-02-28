#!/usr/bin/env python3

import argparse
import sys
import numpy as np
import matplotlib.pyplot as plt
import re
from decimal import Decimal

# Make sure 'associate.py' is Python 3–compatible and in the same folder or in your Python path.
from associate import read_file_list, associate


def align(model, data):
    """
    Align two trajectories using the method of Horn (closed-form).

    Args:
        model (np.matrix): trajectory (3 x n)
        data (np.matrix):  trajectory (3 x n)

    Returns:
        rot          (3x3 np.matrix)
        trans        (3x1 np.matrix)
        trans_error  (np.array of shape (n,)): translational error for each point
        scale        (float): estimated scale factor
    """
    # Center trajectories
    model_zerocentered = model - model.mean(1)
    data_zerocentered  = data  - data.mean(1)

    # Compute W (force double precision here)
    W = np.zeros((3, 3), dtype=np.float64)
    for col in range(model.shape[1]):
        W += np.outer(model_zerocentered[:, col], data_zerocentered[:, col])

    # SVD on W^T
    U, d, Vt = np.linalg.svd(W.T)
    S = np.identity(3, dtype=np.float64)
    # Ensure a proper rotation (det(U) * det(Vt) should be +1)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1
    rot = U @ S @ Vt

    # Scale
    rot_model = rot @ model_zerocentered
    dots = 0.0
    norms = 0.0
    for col in range(data_zerocentered.shape[1]):
        dots  += np.dot(data_zerocentered[:, col].T, rot_model[:, col])
        normi  = np.linalg.norm(model_zerocentered[:, col])
        norms += normi * normi
    # Extract the scalar using .item() to avoid deprecation warnings
    scale = (dots / norms).item() if norms > 1e-12 else 1.0

    # Compute translation
    trans = data.mean(1) - scale * rot @ model.mean(1)

    # Apply alignment
    model_aligned = scale * rot @ model + trans
    alignment_error = model_aligned - data
    trans_error = np.sqrt(np.sum(np.multiply(alignment_error, alignment_error), axis=0)).A1

    return rot, trans, trans_error, scale


def read_metrics_file(filename):
    """
    Read the metrics file into a numpy array.
    The file is assumed to be a CSV with a header row.
    """
    data = np.genfromtxt(filename, delimiter=',', dtype=np.float64, skip_header=1)
    return data


def read_cell_manager_file(filename):
    """
    Parse the cellManager file to extract frame timestamps and FOV Mask dimensions.
    
    The file is expected to contain blocks like:
    
        Frame 1.403640123456e+09 finished in 62.8161 ms stats:
         ...
         FOV Mask: 22x22
    
    This function reads the entire file and uses a regex to capture all such blocks.
    
    Returns:
        tuple: Three lists containing timestamps, FOV mask widths, and FOV mask heights.
    """
    with open(filename, 'r') as f:
        content = f.read()
    # Regex pattern captures:
    #  - The timestamp (with high precision) after "Frame"
    #  - And later the FOV Mask dimensions.
    pattern = r'Frame\s+([\d\.eE\+\-]+)\s+finished\s+in\s+[\d\.]+\s+ms\s+stats:.*?FOV Mask:\s*(\d+)\s*x\s*(\d+)'
    matches = re.findall(pattern, content, flags=re.DOTALL)
    timestamps = []
    fov_widths = []
    fov_heights = []
    for timestamp_str, width_str, height_str in matches:
        # Use Decimal to capture high precision, then convert to float for plotting.
        try:
            ts = float(Decimal(timestamp_str))
        except Exception:
            ts = float(timestamp_str)
        timestamps.append(ts)
        fov_widths.append(int(width_str))
        fov_heights.append(int(height_str))
    return timestamps, fov_widths, fov_heights


def main():
    parser = argparse.ArgumentParser(
        description="""
Compute and plot the translation error of estimated trajectories relative to the ground truth.
The script:
1) Associates the two trajectories by timestamps,
2) Aligns the estimated trajectory (or trajectories) to the ground truth (Horn method),
3) Computes the per-frame translation error,
4) Plots the error vs. time (or frame number) with each estimated file shown in a different color.
Optionally, a metrics file can be used to mark dropped frames and a cellManager file can be used to
plot the FOV Mask size over time.
"""
    )
    parser.add_argument('groundtruth_file',
                        help='Ground truth trajectory file (timestamp tx ty tz qx qy qz qw)')
    parser.add_argument('estimated_files', nargs='+',
                        help='One or more estimated trajectory files (timestamp tx ty tz qx qy qz qw)')
    parser.add_argument('--offset', type=float, default=0.0,
                        help='Time offset added to the timestamps of the estimated file(s) (default: 0.0)')
    parser.add_argument('--scale', type=float, default=1.0,
                        help='Scaling factor to be applied to the estimated trajectory prior to alignment (default: 1.0)')
    parser.add_argument('--max_difference', type=float, default=0.02,
                        help='Max allowed time difference for matching entries (default: 0.02 seconds)')
    parser.add_argument('--plot', type=str, default="trajectory_error.png",
                        help='Output image file to save the trajectory error plot (default: trajectory_error.png)')
    parser.add_argument('--show', action='store_true',
                        help='If set, displays the plot windows instead of saving to file.')
    parser.add_argument('--metrics_file', type=str, default=None,
                        help='Optional metrics file (timestamped) to check for dropped frames (total time == 0)')
    parser.add_argument('--plot_dropped', type=str, default=False,
                        help='Optional output image file to save the plot with dropped frames marked (default: False)')
    parser.add_argument('--use_frame_numbers', action='store_true',
                        help='If set, x-axis will be frame indices (starting at 0) instead of timestamps.')
    parser.add_argument('--ymin', type=float, default=None,
                        help='Minimum y-axis value for the plot (default: auto)')
    parser.add_argument('--ymax', type=float, default=None,
                        help='Maximum y-axis value for the plot (default: auto)')
    # Updated: cellManager now expects a file (not a float)
    parser.add_argument('--cellManager', type=str, default=None,
                        help='Cell Manager output file to plot FOV Mask size over time')
    parser.add_argument('--cellManager_plot', type=str, default="fov_mask_plot.png",
                        help='Output image file for the FOV Mask plot (default: fov_mask_plot.png)')
    parser.add_argument('--title', type=str, default='Trajectory Error Over Time',
                        help='Title of the trajectory error plot (default: Trajectory Error Over Time)')
    args = parser.parse_args()

    # Read the ground truth trajectory once.
    gt_list = read_file_list(args.groundtruth_file)

    # Prepare the main plot.
    fig1, ax1 = plt.subplots()

    # Prepare a colormap for the multiple estimated files.
    num_est = len(args.estimated_files)
    colors = plt.cm.tab10(np.linspace(0, 1, num_est))

    # This variable will track the last x-value (timestamp or frame index) in the estimated data.
    global_max_x = None

    # Process each estimated file.
    for i, est_file in enumerate(args.estimated_files):
        est_list = read_file_list(est_file)
        matches = associate(gt_list, est_list, offset=args.offset, max_difference=args.max_difference)
        if len(matches) < 2:
            print(f"Not enough matching timestamps between ground truth and estimated trajectory in file {est_file}!", file=sys.stderr)
            continue

        # Build matched 3D position arrays (3 x N) with double precision.
        gt_xyz = np.matrix([[float(v) for v in gt_list[a][0:3]]
                            for (a, _) in matches], dtype=np.float64).T
        est_xyz = np.matrix([[float(v) * args.scale for v in est_list[b][0:3]]
                            for (_, b) in matches], dtype=np.float64).T

        # Align the estimated trajectory to the ground truth.
        rot, trans, errors, final_scale = align(est_xyz, gt_xyz)

        # Extract ground truth timestamps from matches using NumPy.
        matches_arr = np.array(matches, dtype=np.float64)
        times = matches_arr[:, 0]

        # Choose x-axis values.
        if args.use_frame_numbers:
            x_vals = np.arange(len(times))
            x_label = 'Frame index'
        else:
            x_vals = times
            x_label = 'Timestamp'

        # Update the global maximum x-value.
        current_max = x_vals.max() if x_vals.size > 0 else None
        if global_max_x is None or (current_max is not None and current_max > global_max_x):
            global_max_x = current_max

        # Plot the translational error for this estimated file.
        match_file = re.search(r'_stereo_inertial_([^_]+)_', est_file)
        run_type = match_file.group(1) if match_file else est_file
        ax1.plot(x_vals, errors, label=f'Error: {run_type}', color=colors[i])

    # Process the metrics file, if provided.
    if args.metrics_file:
        metrics = read_metrics_file(args.metrics_file)
        if metrics is not None and metrics.size > 0:
            metrics_timestamps = metrics[:, 0]
            metrics_values = metrics[:, -1]
            if args.use_frame_numbers:
                x_vals_metrics = list(range(len(metrics_timestamps)))
            else:
                x_vals_metrics = metrics_timestamps.tolist()

            print("First metrics timestamp processed:", metrics_timestamps[0])
            print(f'Final Frame: {global_max_x}')

            dropped_label_added = False
            drop_counter = 0
            total_frame_count = 0
            for x, total_ms in zip(x_vals_metrics, metrics_values):
                total_frame_count += 1
                if global_max_x is not None and x > global_max_x:
                    break
                if total_ms == 0:
                    drop_counter += 1
                    if not dropped_label_added and args.plot_dropped:
                        ax1.axvline(x=x, color='red', linestyle='--', label='Dropped frame')
                        dropped_label_added = True
                    elif args.plot_dropped:
                        ax1.axvline(x=x, color='red', linestyle='--')
            print(f"Total frames: {total_frame_count}")
            print(f"Total dropped frames: {drop_counter}, as a percentage: {drop_counter / total_frame_count * 100:.2f}%")
            print(f"Effective FPS: {total_frame_count / (global_max_x - metrics_timestamps[0]) * 1e9:.2f}")
        else:
            print("Metrics file provided but no valid data found.", file=sys.stderr)
    
    # Set legend, labels, and title for the main plot.
    ax1.legend(loc='upper left')
    if args.ymin is not None:
        plt.ylim(bottom=args.ymin)
    if args.ymax is not None:
        plt.ylim(top=args.ymax)
    plt.title(args.title)
    plt.xlabel(x_label)
    plt.ylabel('Translation error (m)')

    # Process the cellManager file (FOV Mask) if provided.
    if args.cellManager:
        timestamps, fov_widths, fov_heights = read_cell_manager_file(args.cellManager)
        if len(timestamps) > 0:
            fig2, ax2 = plt.subplots()
            ax2.scatter(timestamps, fov_widths, color='blue', label='FOV Mask Dimension', marker='o')
            #ax2.scatter(timestamps, fov_heights, color='red', label='FOV Mask Height', marker='o')
            ax2.set_title('FOV Mask Size Over Time')
            ax2.set_xlabel('Timestamp')
            ax2.set_ylabel('FOV Mask Dimension')
            ax2.legend()
        else:
            print("No valid FOV Mask data found in cellManager file.", file=sys.stderr)

    # Show or save the plots.
    if args.show:
        plt.show()
    else:
        fig1.savefig(args.plot, dpi=150)
        print(f"Saved trajectory error plot to {args.plot}")
        if args.cellManager and args.cellManager_plot:
            fig2.savefig(args.cellManager_plot, dpi=150)
            print(f"Saved FOV Mask plot to {args.cellManager_plot}")


if __name__ == "__main__":
    main()