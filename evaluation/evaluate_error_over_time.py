#!/usr/bin/env python3
"""
evaluate_error_over_time.py  –  trajectory-error visualiser.

trajectory_errors_wide.csv now supports columns:
  normal, normal_stress, oasis, oasis_stress,
  deadlines, omega_slam_deadlines, pid_slam_deadlines, slimslam_deadlines
"""
# --------------------------------------------------------------------------
import argparse, os, re, sys, statistics
from decimal import Decimal
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from associate import read_file_list, associate
# --------------------------------------------------------------------------
def align(model: np.matrix, data: np.matrix) -> np.ndarray:
    """Aligns two trajectories using the method of Horn (1987)."""
    m0, d0 = model - model.mean(1), data - data.mean(1)
    W = sum(np.outer(m0[:, c], d0[:, c]) for c in range(model.shape[1]))
    U, _, Vt = np.linalg.svd(W.T)
    S = np.identity(3); S[2, 2] *= -1 if np.linalg.det(U) * np.linalg.det(Vt) < 0 else 1
    R = U @ S @ Vt
    dots  = sum(np.dot(d0[:, c].T, R @ m0[:, c]) for c in range(d0.shape[1]))
    norms = sum(np.linalg.norm(m0[:, c]) ** 2      for c in range(m0.shape[1]))
    s = float(dots / norms) if norms > 1e-12 else 1.0
    t = data.mean(1) - s * R @ model.mean(1)
    e = (s * R @ model + t) - data
    return np.sqrt(np.sum(np.multiply(e, e), axis=0)).A1
# --------------------------------------------------------------------------
def read_metrics_file(p): return np.genfromtxt(p, delimiter=',', dtype=np.float64, skip_header=1)
def read_cell_manager_file(p):
    pat = r'Frame\s+([\d\.eE+\-]+).*?FOV Mask:\s*(\d+)\s*x\s*\d+'
    ts, w = [], []
    with open(p, 'r') as f:
        for t, ww in re.findall(pat, f.read(), flags=re.DOTALL):
            ts.append(float(Decimal(t))); w.append(int(ww))
    return ts, w
def _unique(base, existing):
    """Ensures a column name is unique by appending _2, _3, etc. if needed."""
    if base not in existing: return base
    i = 2
    while f"{base}_{i}" in existing: i += 1
    return f"{base}_{i}"
# --------------------------------------------------------------------------
# Identify run-type (oasis, deadlines, fov_10, fov_deadlines_10, slimslam_easy…)
RUN_RE = re.compile(
    r'[/_](?:'
    r'(normal(?:_stress)?)|'                                   # 1  normal / normal_stress
    r'(oasis(?:_stress)?)|'                                    # 2
    r'(fov(?:_deadlines)?_[0-9]+)|'                            # 3  fov_10 / fov_deadlines_8
    r'((?:omega|pid)_slam_deadlines)|'                         # 4
    r'(slimslam(?:_deadlines)?_[^_/]+)|'                       # 5  slimslam_easy …
    r'(deadlines)'                                             # 6
    r')(?:_|/)', re.I)
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('groundtruth_file')
    ap.add_argument('estimated_files', nargs='+')
    ap.add_argument('--offset', type=float, default=0.0)
    ap.add_argument('--scale',  type=float, default=1.0)
    ap.add_argument('--max_difference', type=float, default=0.02)
    ap.add_argument('--plot', default='trajectory_error.png')
    ap.add_argument('--show', action='store_true')
    ap.add_argument('--metrics_file')
    ap.add_argument('--plot_dropped', action='store_true')
    ap.add_argument('--use_frame_numbers', action='store_true')
    ap.add_argument('--ymin', type=float)
    ap.add_argument('--ymax', type=float)
    ap.add_argument('--cellManager')
    ap.add_argument('--cellManager_plot', default='fov_mask_plot.png')
    ap.add_argument('--title', default='Trajectory Error Over Time')
    # Add an argument to accept explicit names for the trajectories.
    ap.add_argument('--trajectory_names', help='Comma-separated list of names for the output columns')
    args = ap.parse_args()

    # If trajectory_names are provided, split them into a list.
    # If the count doesn't match the file count, print a warning and fall back to the old method.
    trajectory_names = None
    if args.trajectory_names:
        names = args.trajectory_names.split(',')
        if len(names) == len(args.estimated_files):
            trajectory_names = names
        else:
            print(f"⚠️  Warning: --trajectory_names count ({len(names)}) does not match "
                  f"file count ({len(args.estimated_files)}). Falling back to automatic naming.", file=sys.stderr)

    gt_list = read_file_list(args.groundtruth_file)

    fig, ax = plt.subplots()
    cmap = plt.cm.tab10(np.linspace(0, 1, len(args.estimated_files)))

    xcol = 'frame_index' if args.use_frame_numbers else 'timestamp'
    wide_df = pd.DataFrame()

    for idx, est_path in enumerate(args.estimated_files):
        # If explicit names are available and valid, use them. Otherwise, use the original regex method.
        if trajectory_names:
            run_type = trajectory_names[idx]
        else:
            m = RUN_RE.search(est_path)
            run_type = m.group(0)[1:-1].lower() if m else os.path.splitext(os.path.basename(est_path))[0]
        
        # Ensure the column name is unique, which is still needed in case the user provides duplicates.
        run_type = _unique(run_type, wide_df.columns)

        est_list = read_file_list(est_path)
        matches  = associate(gt_list, est_list,
                             offset=args.offset,
                             max_difference=args.max_difference)
        if len(matches) < 2:
            print(f"✗  {run_type}: not enough matches", file=sys.stderr)
            continue

        gt_xyz  = np.matrix([[float(v) for v in gt_list[a][0:3]]
                             for a, _ in matches]).T
        est_xyz = np.matrix([[float(v)*args.scale for v in est_list[b][0:3]]
                             for _, b in matches]).T
        err = align(est_xyz, gt_xyz)

        t = np.array(matches, float)[:, 0]
        x = np.arange(len(t)) if args.use_frame_numbers else t
        ax.plot(x, err, label=f'Error: {run_type}', color=cmap[idx])

        run_df = pd.DataFrame({xcol: x, run_type: err}).set_index(xcol)
        wide_df = run_df if wide_df.empty else wide_df.join(run_df, how='outer')

    if not wide_df.empty:
        # Interpolate missing values (NaNs) that can occur from joining data of different lengths.
        # This makes the resulting CSV cleaner and more usable for analysis.
        wide_df.interpolate(method='linear', limit_direction='both', inplace=True)
        wide_df.sort_index().reset_index().to_csv('trajectory_errors_wide.csv', index=False)
        print("✓ trajectory_errors_wide.csv written (columns:", ", ".join(wide_df.columns), ")")


# --------------------------------------------------------------------------
if __name__ == '__main__':
    main()
