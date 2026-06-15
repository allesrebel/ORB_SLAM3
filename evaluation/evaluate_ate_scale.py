#!/usr/bin/env python3
"""
evaluate_ate_scale.py  –  ATE + scale evaluator with timestamp interpolation.

Outputs:
    trajectory_pair.csv             (wide table: GT + aligned estimate)
    ground_truth_traj.csv
    estimated_traj_aligned.csv
    difference_segments.csv
"""
# --------------------------------------------------------------------------
import sys, argparse
import numpy as np
import pandas as pd
import associate
# --------------------------------------------------------------------------
def interp_xyz(sample_dict, stamps, scale=1.0):
    """Linear interpolation of (x,y,z) at the requested stamps."""
    keys = np.array(sorted(sample_dict.keys()), float)
    xyz  = np.array([[float(v) for v in sample_dict[k][0:3]] for k in keys])
    out  = np.empty((len(stamps), 3))
    for ax in range(3):
        out[:, ax] = np.interp(stamps, keys, xyz[:, ax])
    return np.matrix(out * scale).T   # shape (3 × N)

# --------------------------------------------------------------------------
def align(model, data):
    """Horn matching. Returns transforms & per-frame errors."""
    m0, d0 = model - model.mean(1), data - data.mean(1)
    W = sum(np.outer(m0[:, c], d0[:, c]) for c in range(model.shape[1]))
    U, _, Vt = np.linalg.svd(W.T)
    S = np.identity(3);  S[2, 2] *= -1 if np.linalg.det(U) * np.linalg.det(Vt) < 0 else 1
    R = U @ S @ Vt

    dots, norms = 0.0, 0.0
    for c in range(d0.shape[1]):
        dots  += float(np.dot(d0[:, c].T, R @ m0[:, c]))  # -> scalar
        norms += float(np.linalg.norm(m0[:, c])**2)
    s = dots / norms if norms > 1e-12 else 1.0

    tGT = data.mean(1) - s * R @ model.mean(1)
    t   = data.mean(1) -     R @ model.mean(1)

    m_alnGT = s * R @ model + tGT
    m_aln   =     R @ model + t

    errGT = np.sqrt(np.sum(np.multiply(m_alnGT - data,
                                       m_alnGT - data), axis=0)).A1
    err   = np.sqrt(np.sum(np.multiply(m_aln   - data,
                                       m_aln   - data), axis=0)).A1
    return R, tGT, errGT, t, err, s
# --------------------------------------------------------------------------
if __name__ == "__main__":
    pa = argparse.ArgumentParser()
    pa.add_argument('first_file')           # ground truth
    pa.add_argument('second_file')          # estimated
    pa.add_argument('--offset', type=float, default=0.0)
    pa.add_argument('--scale',  type=float, default=1.0)
    pa.add_argument('--max_difference', type=int, default=20_000_000)
    pa.add_argument('--plot')
    pa.add_argument('--verbose', action='store_true')
    pa.add_argument('--csv', action='store_true')
    pa.add_argument('--verbose2', action='store_true')
    pa.add_argument('--save'); pa.add_argument('--save_associations')
    args = pa.parse_args()

    # ---------- load the two TUM files ------------------------------------
    gt_list  = associate.read_file_list(args.first_file,  False)
    est_list = associate.read_file_list(args.second_file, False)

    # ---------- common timeline (use GT stamps that lie inside EST span) --
    gt_stamps  = np.array(sorted(gt_list.keys()), float)
    est_stamps = np.array(sorted(est_list.keys()), float)
    if est_stamps.size < 2:
        sys.exit("Estimated trajectory has < 2 poses")
    common_stamps = gt_stamps[(gt_stamps >= est_stamps[0]) &
                              (gt_stamps <= est_stamps[-1])]
    if common_stamps.size < 2:
        sys.exit("Not enough overlapping timestamps for interpolation")

    # ---------- build XYZ matrices (interpolated) -------------------------
    gt_xyz  = np.matrix([[float(v) for v in gt_list[s][0:3]]
                         for s in common_stamps]).T
    est_xyz = interp_xyz(est_list, common_stamps, scale=args.scale)

    # ---------- consistency + errors ----------------------------------------
    R, tGT, errGT, t, err, scl = align(est_xyz, gt_xyz)
    est_xyz_aln = scl * R @ est_xyz + t

    # ---------- wide CSV: GT + aligned estimate ---------------------------
    pair_rows = []
    for ts, (xg, yg, zg), (xe, ye, ze) in zip(
        common_stamps, gt_xyz.T.A, est_xyz_aln.T.A):
        pair_rows.append({"timestamp_gt": ts, "x_gt": xg, "y_gt": yg, "z_gt": zg,
                          "timestamp_est": ts, "x_est": xe, "y_est": ye, "z_est": ze})
    pd.DataFrame(pair_rows).to_csv("trajectory_pair.csv", index=False)

    # ---------- legacy CSVs (unchanged) -----------------------------------
    first_stamps  = np.array(sorted(gt_list.keys()), float)
    gt_full_xyz   = np.matrix([[float(v) for v in gt_list[s][0:3]]
                               for s in first_stamps]).T

    second_stamps = np.array(sorted(est_list.keys()), float)
    est_full_xyz  = np.matrix([[float(v)*args.scale for v in est_list[s][0:3]]
                               for s in second_stamps]).T
    est_full_aln  = scl * R @ est_full_xyz + t
    if args.csv:
        pd.DataFrame({
            "timestamp": first_stamps,
            "x": gt_full_xyz.T[:, 0].A1,
            "y": gt_full_xyz.T[:, 1].A1,
            "z": gt_full_xyz.T[:, 2].A1,
        }).to_csv("ground_truth_traj.csv", index=False)

        pd.DataFrame({
            "timestamp": second_stamps,
            "x": est_full_aln.T[:, 0].A1,
            "y": est_full_aln.T[:, 1].A1,
            "z": est_full_aln.T[:, 2].A1,
        }).to_csv("estimated_traj_aligned.csv", index=False)

        pd.DataFrame(pair_rows).to_csv("difference_segments.csv", index=False)

    # ---------- console output --------------------------------------------
    if args.verbose:
        print("compared_pose_pairs", len(err))
        print("absolute_translational_error.rmse",
              np.sqrt((err @ err) / len(err)), "m")
        print("absolute_translational_error.mean",   np.mean(err),   "m")
        print("absolute_translational_error.median", np.median(err), "m")
        print("absolute_translational_error.std",    np.std(err),    "m")
        print("absolute_translational_error.min",    np.min(err),    "m")
        print("absolute_translational_error.max",    np.max(err),    "m")
        print("max idx:", int(np.argmax(err)))
    else:
        rmse_scaled = np.sqrt((err @ err) / len(err))
        rmse_noscl  = np.sqrt((errGT @ errGT) / len(errGT))
        print(f"{rmse_scaled},{scl},{rmse_noscl}")

    if args.verbose2:
        print("absolute_translational_error.rmse",
              np.sqrt((err @ err) / len(err)), "m")
        print("absolute_translational_errorGT.rmse",
              np.sqrt((errGT @ errGT) / len(errGT)), "m")

    # ---------- optional plot ---------------------------------------------
    if args.plot:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.plot(gt_full_xyz.T[:, 0], gt_full_xyz.T[:, 1],
                '-', color='black', label='ground truth')
        ax.plot(est_full_aln.T[:, 0], est_full_aln.T[:, 1],
                '-', color='blue',  label='estimated')
        for (xg, yg, _), (xe, ye, _) in zip(gt_xyz.T.A, est_xyz_aln.T.A):
            ax.plot([xg, xe], [yg, ye], '-', color='red', label='_nolegend_')
        ax.set_xlabel('x [m]'); ax.set_ylabel('y [m]')
        ax.set_aspect('equal'); ax.legend()
        fig.savefig(args.plot, dpi=150)
