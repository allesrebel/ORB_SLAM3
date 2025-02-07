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

    # Compute W
    W = np.zeros((3, 3))
    for col in range(model.shape[1]):
        W += np.outer(model_zerocentered[:, col], data_zerocentered[:, col])

    # SVD on W^T
    U, d, Vt = np.linalg.svd(W.T)
    S = np.identity(3)
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
            try:
                # The first column is the timestamp (in ns, as float string)
                # The last column is the "Total[ms]" we want to plot
                timestamp_str = parts[0]
                total_str     = parts[-1]
                timestamp_s = float(timestamp_str)
                total_ms    = float(total_str)

                metrics_dict[timestamp_s] = total_ms
            except (ValueError, IndexError):
                continue
    return metrics_dict


def main():
    parser = argparse.ArgumentParser(
        description="""
Compute and plot the translation error of estimated trajectories relative to the ground truth.
The script:
1) Associates the two trajectories by timestamps,
2) Aligns the estimated trajectory (or trajectories) to the ground truth (Horn method),
3) Computes the per-frame translation error,
4) Plots the error vs. time (or frame number) with each estimated file shown in a different color.
Optionally, an additional metrics file can be plotted on a secondary y-axis.
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
                        help='Optional metrics file (timestamped) to plot on the same figure')
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

    # Process each estimated file.
    for i, est_file in enumerate(args.estimated_files):
        est_list = read_file_list(est_file)
        matches = associate(gt_list, est_list, offset=args.offset, max_difference=args.max_difference)
        if len(matches) < 2:
            print(f"Not enough matching timestamps between ground truth and estimated trajectory in file {est_file}!", file=sys.stderr)
            continue

        # Build matched 3D position arrays (3 x N)
        gt_xyz = np.matrix([[float(v) for v in gt_list[a][0:3]]
                            for (a, _) in matches]).T
        est_xyz = np.matrix([[float(v) * args.scale for v in est_list[b][0:3]]
                             for (_, b) in matches]).T

        # Align the estimated trajectory to the ground truth.
        rot, trans, errors, final_scale = align(est_xyz, gt_xyz)

        # Use the ground truth timestamps from the association.
        times = [a for (a, _) in matches]
        # Sort by time to ensure correct order.
        time_error_pairs = sorted(zip(times, errors), key=lambda x: x[0])
        times_sorted = [p[0] for p in time_error_pairs]
        errors_sorted = [p[1] for p in time_error_pairs]

        # Choose x-axis values.
        if args.use_frame_numbers:
            x_vals = list(range(len(times_sorted)))
            x_label = 'Frame index'
        else:
            x_vals = times_sorted
            x_label = 'Timestamp'

        # Plot the translational error for this estimated file.
        # Extract the run type from the file name using regex
        match = re.search(r'_stereo_inertial_([^_]+)_', est_file)
        run_type = match.group(1) if match else est_file
        ax1.plot(x_vals, errors_sorted, label=f'Error: {run_type}', color=colors[i])

    if args.ymin is not None or args.ymax is not None:
        ax1.set_ylim(bottom=args.ymin, top=args.ymax)
    ax1.set_xlabel(x_label)
    ax1.set_ylabel('Translation Error (m)', color='black')
    ax1.grid(True)
    ax1.tick_params(axis='y', labelcolor='black')
    ax1.set_title(args.title)

    # Process the metrics file, if provided.
    if args.metrics_file:
        metrics_dict = read_metrics_file(args.metrics_file)
        if metrics_dict:
            # Sort the metrics by timestamp.
            sorted_metrics = sorted(metrics_dict.items(), key=lambda kv: kv[0])
            metrics_timestamps = [kv[0] for kv in sorted_metrics]
            metrics_values = [kv[1] for kv in sorted_metrics]
            if args.use_frame_numbers:
                x_vals_metrics = list(range(len(metrics_timestamps)))
            else:
                x_vals_metrics = metrics_timestamps

            ax2 = ax1.twinx()
            ax2.plot(x_vals_metrics, metrics_values, label='Total[ms]', color='red')
            ax2.set_ylabel('Total (ms)', color='red')
            ax2.tick_params(axis='y', labelcolor='red')

            # Combine legends from both axes.
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        else:
            print("Metrics file provided but no valid data found.", file=sys.stderr)
    else:
        ax1.legend(loc='upper left')

    # Show or save the plot.
    if args.show:
        plt.show()
    else:
        plt.savefig(args.plot, dpi=150)
        print(f"Saved plot to {args.plot}")


if __name__ == "__main__":
    main()