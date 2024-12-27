#!/usr/bin/env python3

import argparse
import sys
import numpy as np
import matplotlib.pyplot as plt

# Import the associate functions from the separate module.
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
    args = parser.parse_args()

    # 1) Read the trajectories
    gt_list  = read_file_list(args.groundtruth_file)  # stamp -> [tx, ty, tz, qx, qy, qz, qw]
    est_list = read_file_list(args.estimated_file)     # stamp -> [tx, ty, tz, qx, qy, qz, qw]

    # 2) Associate by timestamps
    matches = associate(gt_list, est_list, offset=args.offset, max_difference=args.max_difference)
    if len(matches) < 2:
        sys.exit("Not enough matching timestamps between groundtruth and estimated trajectory!")

    # 3) Build matched 3D position arrays
    #    We take the first 3 entries [tx, ty, tz] from each matched sample
    #    shape: (3, N)
    gt_xyz  = np.matrix([[float(v) for v in gt_list[a][0:3]] 
                         for (a, _) in matches]).T
    est_xyz = np.matrix([[float(v) * args.scale for v in est_list[b][0:3]] 
                         for (_, b) in matches]).T

    # 4) Align the estimated points to the ground truth
    rot, trans, errors, final_scale = align(est_xyz, gt_xyz)

    # 5) Once aligned, compute the per-frame error and get the timestamps
    #    The `errors` array from align() is the 3D distance error per matched index
    #    For plotting vs. time, we'll just use the groundtruth stamps (a)
    times = [a for (a, _) in matches]

    # Sort by time if needed (they should already be sorted by 'associate', but just to be safe)
    # We'll make a single list of (time, error), then sort by time
    time_error_pairs = sorted(zip(times, errors), key=lambda x: x[0])

    # Unzip into separate lists
    times_sorted  = [p[0] for p in time_error_pairs]
    errors_sorted = [p[1] for p in time_error_pairs]

    # 6) Plot the time vs error
    plt.figure()
    plt.plot(times_sorted, errors_sorted, label='Translational Error', color='blue')
    plt.xlabel('Time (s)')
    plt.ylabel('Translation Error (m)')
    plt.title('Trajectory Translation Error Over Time')
    plt.grid(True)
    plt.legend()

    # 7) Save or show
    if args.show:
        plt.show()
    else:
        plt.savefig(args.plot, dpi=150)
        print(f"Saved plot to {args.plot}")


if __name__ == "__main__":
    main()

