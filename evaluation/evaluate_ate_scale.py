#!/usr/bin/env python3
"""
evaluate_ate_scale.py  –  ATE + scale evaluator.

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
def align(model, data):
    """Horn alignment. Returns transforms & per-frame errors."""
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
    pa.add_argument('--verbose2', action='store_true')
    pa.add_argument('--save'); pa.add_argument('--save_associations')
    args = pa.parse_args()

    gt_list  = associate.read_file_list(args.first_file,  False)
    est_list = associate.read_file_list(args.second_file, False)
    matches  = associate.associate(gt_list, est_list,
                                   args.offset, args.max_difference)
    if len(matches) < 2:
        sys.exit("Not enough matching timestamps")

    # --- build XYZ matrices ------------------------------------------------
    gt_xyz  = np.matrix([[float(v) for v in gt_list[a][0:3]]
                         for a, _ in matches]).T
    est_xyz = np.matrix([[float(v)*args.scale for v in est_list[b][0:3]]
                         for _, b in matches]).T

    R, tGT, errGT, t, err, scl = align(est_xyz, gt_xyz)
    est_xyz_aln = scl * R @ est_xyz + t

    # ---------- wide CSV: GT + aligned estimate ---------------------------
    pair_rows = []
    for (tg, te), (xg, yg, zg), (xe, ye, ze) in zip(
        matches, gt_xyz.T.A, est_xyz_aln.T.A):
        pair_rows.append({"timestamp_gt": tg, "x_gt": xg, "y_gt": yg, "z_gt": zg,
                          "timestamp_est": te, "x_est": xe, "y_est": ye, "z_est": ze})
    pd.DataFrame(pair_rows).to_csv("trajectory_pair.csv", index=False)

    # ---------- legacy CSVs -----------------------------------------------
    first_stamps  = np.array(sorted(gt_list.keys()), float)
    gt_full_xyz   = np.matrix([[float(v) for v in gt_list[s][0:3]]
                               for s in first_stamps]).T

    second_stamps = np.array(sorted(est_list.keys()), float)
    est_full_xyz  = np.matrix([[float(v)*args.scale for v in est_list[s][0:3]]
                               for s in second_stamps]).T
    est_full_aln  = scl * R @ est_full_xyz + t

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
        ax.plot(gt_full_xyz.T[:,0], gt_full_xyz.T[:,1],
                '-', color='black', label='ground truth')
        ax.plot(est_full_aln.T[:,0], est_full_aln.T[:,1],
                '-', color='blue',  label='estimated')
        for (xg, yg, _), (xe, ye, _) in zip(gt_xyz.T.A, est_xyz_aln.T.A):
            ax.plot([xg, xe], [yg, ye], '-', color='red', label='_nolegend_')
        ax.set_xlabel('x [m]'); ax.set_ylabel('y [m]')
        ax.set_aspect('equal'); ax.legend()
        fig.savefig(args.plot, dpi=150)
