#!/usr/bin/env python3

import argparse
import sys
import numpy as np
import matplotlib.pyplot as plt

# Make sure 'associate.py' is Python 3–compatible and in the same folder or in your Python path.
from associate import read_file_list, associate
import re


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
    
    Example file:
    #Frame Timestamp[ns],Image Rect[ms],Image Resize[ms],ORB ext[ms],
    #Stereo match[ms],IMU preint[ms],Pose pred[ms],LM track[ms],
    #KF dec[ms],Total[ms]
    1403636579763555584.000000,0.000000,0.000000,26.484096,5.044527,0.004576,15.036108,8.526757,0.003296,34.782721
    1403636579813555456.000000,0.000000,0.000000,24.773028,5.298355,0.083489,4.532519,8.118047,0.001120,34.077975
    ...
    
    Returns:
        numpy.ndarray: Array with each row representing a metric entry.
    """
    data = np.genfromtxt(filename, delimiter=',', dtype=np.float64, skip_header=1)

    return data


def main():
    parser = argparse.ArgumentParser(
        description="""
Compute and plot the translation error of estimated trajectories relative to the ground truth.
The script:
1) Associates the two trajectories by timestamps,
2) Aligns the estimated trajectory (or trajectories) to the ground truth (Horn method),
3) Computes the per-frame translation error,
4) Plots the error vs. time (or frame number) with each estimated file shown in a different color.
Optionally, an additional metrics file can be used to mark dropped frames (total time == 0),
but only up to the last timestamp present in the estimated data.
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
                        help='Output image file to save the plot (default: trajectory_error.png)')
    parser.add_argument('--show', action='store_true',
                        help='If set, displays the plot window instead of saving to a file.')
    parser.add_argument('--metrics_file', type=str, default=None,
                        help='Optional metrics file (timestamped) to check for dropped frames (total time == 0)')
    parser.add_argument('--plot_dropped', type=str, default=False,
                        help='Optional output image file to save the plot with dropped frames marked (default: False)')
    parser.add_argument('--use_frame_numbers', action='store_true',
                        help='If set, x-axis will be frame indices (starting at 0) instead of timestamps.')
    parser.add_argument('--ymin', type=float, default=None,
                        help='Minimum y-axis value for the plot (default: auto)')
    parser.add_argument('--title', type=str, default='Trajectory Error Over Time',
                        help='Title of the plot (default: Trajectory Error Over Time)')
    parser.add_argument('--ymax', type=float, default=None,
                        help='Maximum y-axis value for the plot (default: auto)')
    args = parser.parse_args()

    # Read the ground truth trajectory once.
    gt_list = read_file_list(args.groundtruth_file)

    # Prepare the plot.
    fig, ax1 = plt.subplots()

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
        # Assume matches are already sorted by timestamp.
        matches_arr = np.array(matches, dtype=np.float64)  # shape (N, 2)
        times = matches_arr[:, 0]  # Timestamps

        # No need to sort since they're already in order.
        times_sorted = times
        errors_sorted = errors  # Errors are in the same order as matches.

        # Choose x-axis values.
        if args.use_frame_numbers:
            x_vals = np.arange(len(times_sorted))
            x_label = 'Frame index'
        else:
            x_vals = times_sorted
            x_label = 'Timestamp'

        # Update the global maximum x-value.
        current_max = x_vals.max() if x_vals.size > 0 else None
        if global_max_x is None or (current_max is not None and current_max > global_max_x):
            global_max_x = current_max

        # Plot the translational error for this estimated file.
        match_file = re.search(r'_stereo_inertial_([^_]+)_', est_file)
        run_type = match_file.group(1) if match_file else est_file
        ax1.plot(x_vals, errors_sorted, label=f'Error: {run_type}', color=colors[i])


    # Process the metrics file, if provided.
    if args.metrics_file:
        metrics = read_metrics_file(args.metrics_file)
        if metrics is not None and metrics.size > 0:
            # Assume the metrics array is already sorted by timestamp.
            metrics_timestamps = metrics[:, 0]
            metrics_values = metrics[:, -1]

            if args.use_frame_numbers:
                x_vals_metrics = list(range(len(metrics_timestamps)))
            else:
                x_vals_metrics = metrics_timestamps.tolist()

            # Debug: print out the first timestamp that gets processed.
            print("First metrics timestamp processed:", metrics_timestamps[0])
            print(f'Final Frame: {global_max_x}')

            dropped_label_added = False
            drop_counter = 0
            total_frame_count = 0
            for x, total_ms in zip(x_vals_metrics, metrics_values):
                # Only consider metrics within the estimated data range.
                total_frame_count += 1
                if global_max_x is not None and x > global_max_x:
                    break # we're past the last estimated timestamp
                if total_ms == 0:
                    drop_counter += 1
                    # Only add the label once to avoid duplicate legend entries.
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
    
    # Display legend from the main axis.
    ax1.legend(loc='upper left')

    # Show or save the plot.
    if args.show:
        plt.show()
    else:
        plt.savefig(args.plot, dpi=150)
        print(f"Saved plot to {args.plot}")


if __name__ == "__main__":
    main()