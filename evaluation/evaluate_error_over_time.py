#!/usr/bin/env python3

import argparse
import sys
import numpy as np
import matplotlib.pyplot as plt

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

    # Compute W
    W = np.zeros((3,3))
    for col in range(model.shape[1]):
        W += np.outer(model_zerocentered[:, col], data_zerocentered[:, col])

    # SVD on W^T
    U, d, Vt = np.linalg.svd(W.T)
    S = np.identity(3)
    # Ensure a proper rotation (det(U) * det(Vt) should be +1)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2,2] = -1
    rot = U @ S @ Vt

    # Scale
    rot_model = rot @ model_zerocentered
    dots  = 0.0
    norms = 0.0
    for col in range(data_zerocentered.shape[1]):
        dots  += np.dot(data_zerocentered[:, col].T, rot_model[:, col])
        normi  = np.linalg.norm(model_zerocentered[:, col])
        norms += normi * normi
    scale = float(dots / norms) if norms > 1e-12 else 1.0

    # Compute translation
    trans = data.mean(1) - scale * rot @ model.mean(1)

    # Apply alignment
    model_aligned = scale * rot @ model + trans
    alignment_error = model_aligned - data
    trans_error = np.sqrt(np.sum(np.multiply(alignment_error, alignment_error), axis=0)).A1

    return rot, trans, trans_error, scale


def read_metrics_file(filename):
    """
    Read the metrics file (the additional text file) into a dict:
       timestamp -> total_ms_value

    Expected lines look like:
      1403636579763555584.000000,0.000000,0.000000,13.863084,5.118943,0.004608,9.826650,6.913653,0.004288,21.885552
    with a header line that starts with '#'.
    """
    metrics_dict = {}
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments or empty lines
            if not line or line.startswith('#'):
                continue

            parts = line.split(',')
            # The first column is the timestamp (in ns, as float string)
            # The last column is the "Total[ms]" we want to plot
            try:
                timestamp_str = parts[0]
                total_str     = parts[-1]
                timestamp_s = float(timestamp_str)
                total_ms    = float(total_str)

                metrics_dict[timestamp_s] = total_ms
            except (ValueError, IndexError):
                # If there's a parsing error, skip that line or handle differently
                continue
    return metrics_dict


def main():
    parser = argparse.ArgumentParser(
        description="""
Compute and plot the translation error of the estimated trajectory over time 
relative to the ground truth. The script:
1) Associates the two trajectories by timestamps,
2) Aligns the estimated trajectory to the ground truth (Horn method),
3) Computes the per-frame translation error,
4) Plots the error vs. time.
"""
    )
    parser.add_argument('groundtruth_file', 
                        help='Ground truth trajectory file (timestamp tx ty tz qx qy qz qw)')
    parser.add_argument('estimated_file', 
                        help='Estimated trajectory file (timestamp tx ty tz qx qy qz qw)')
    parser.add_argument('--offset', type=float, default=0.0,
                        help='Time offset added to the timestamps of the estimated file (default: 0.0)')
    parser.add_argument('--scale', type=float, default=1.0,
                        help='Scaling factor to be applied to the estimated trajectory prior to alignment (default: 1.0)')
    parser.add_argument('--max_difference', type=float, default=0.02,
                        help='Max allowed time difference for matching entries (default: 0.02 seconds)')
    parser.add_argument('--plot', type=str, default="trajectory_error.png",
                        help='Output image file to save the plot (default: trajectory_error.png)')
    parser.add_argument('--show', action='store_true',
                        help='If set, displays the plot window instead of saving to a file.')
    # New argument for the additional metrics file
    parser.add_argument('--metrics_file', type=str, default=None,
                        help='Optional metrics file (timestamped) to plot on the same figure (e.g., #Frame Timestamp[ns],...,Total[ms])')
    # New argument to switch the x-axis from timestamps to frame numbers
    parser.add_argument('--use_frame_numbers', action='store_true',
                        help='If set, x-axis will be frame indices (starting at 0) instead of timestamps.')
    args = parser.parse_args()

    # 1) Read the trajectories
    gt_list  = read_file_list(args.groundtruth_file)  # stamp -> [tx, ty, tz, qx, qy, qz, qw]
    est_list = read_file_list(args.estimated_file)     # stamp -> [tx, ty, tz, qx, qy, qz, qw]

    # 2) Associate by timestamps
    matches = associate(gt_list, est_list, offset=args.offset, max_difference=args.max_difference)
    if len(matches) < 2:
        sys.exit("Not enough matching timestamps between groundtruth and estimated trajectory!")

    # 3) Build matched 3D position arrays (3,N)
    gt_xyz  = np.matrix([[float(v) for v in gt_list[a][0:3]] 
                         for (a, _) in matches]).T
    est_xyz = np.matrix([[float(v) * args.scale for v in est_list[b][0:3]] 
                         for (_, b) in matches]).T

    # 4) Align the estimated points to the ground truth
    rot, trans, errors, final_scale = align(est_xyz, gt_xyz)

    # 5) Once aligned, we have the 3D error per matched index
    #    For plotting vs. time, we'll just use the groundtruth stamps
    times = [a for (a, _) in matches]

    # Sort by time, just to be sure
    time_error_pairs = sorted(zip(times, errors), key=lambda x: x[0])
    times_sorted  = [p[0] for p in time_error_pairs]
    errors_sorted = [p[1] for p in time_error_pairs]

    # 6) Optionally parse the metrics file
    if args.metrics_file:
        metrics_dict = read_metrics_file(args.metrics_file)
    else:
        metrics_dict = None

    # -- At this point, we have all the data (errors vs. times, plus optional metrics).
    #    Now we decide if we want to switch the x-axis from timestamps to frame numbers.

    if args.use_frame_numbers:
        # Replace the time stamps with frame indices
        # frames_sorted will be [0, 1, 2, ..., N-1]
        frames_sorted = list(range(len(times_sorted)))
        x_vals_error = frames_sorted
        x_label = 'Frame index'
    else:
        # Use the original timestamps
        x_vals_error = times_sorted
        x_label = 'Time (s)'

    # For plotting the metrics, we need to handle the x-values carefully
    #   if we are using frames, we plot them by frame index
    #   otherwise, we plot them by the original timestamp.
    # We'll store them in "x_vals_metrics" and "metrics_vals" below:
    x_vals_metrics = []
    metrics_vals   = []

    if metrics_dict is not None:
        # If using timestamps, we collect (timestamp, metric).
        # If using frames, we collect (frame_index, metric).
        if args.use_frame_numbers:
            # We'll only plot metrics for frames that also appear in times_sorted
            for i, t in enumerate(times_sorted):
                if t in metrics_dict:
                    x_vals_metrics.append(i)                   # the frame index
                    metrics_vals.append(metrics_dict[t])       # total ms
        else:
            # We'll directly use the timestamps
            for t in times_sorted:
                if t in metrics_dict:
                    x_vals_metrics.append(t)
                    metrics_vals.append(metrics_dict[t])

    # 7) Plot
    fig, ax1 = plt.subplots()
    ax1.plot(x_vals_error, errors_sorted, label='Translational Error (m)', color='blue')
    ax1.set_xlabel(x_label)
    ax1.set_ylabel('Translation Error (m)', color='blue')
    ax1.grid(True)
    ax1.tick_params(axis='y', labelcolor='blue')

    if metrics_dict is not None:
        ax2 = ax1.twinx()
        ax2.plot(x_vals_metrics, metrics_vals, label='Total[ms]', color='red')
        ax2.set_ylabel('Total (ms)', color='red')
        ax2.tick_params(axis='y', labelcolor='red')

        # Combined legend
        lines_1, labels_1 = ax1.get_legend_handles_labels()
        lines_2, labels_2 = ax2.get_legend_handles_labels()
        ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')
    else:
        # If no metrics file provided, just one legend
        ax1.legend(loc='upper left')

    # 8) Save or show
    if args.show:
        plt.show()
    else:
        plt.savefig(args.plot, dpi=150)
        print(f"Saved plot to {args.plot}")


if __name__ == "__main__":
    main()
