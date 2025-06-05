#!/usr/bin/env python3
"""
generate_control_file.py   –   now with RMSE + ExecTime tie-breaker
FOR Debug Mode: SLAM_LOGLEVEL=DEBUG ./process_slimslam_training.sh
"""

import os, re, sys, argparse, logging
from collections import Counter
import numpy as np
# ─────────────────────────────────────────────────────────────────────────────
def _init_logger(level="INFO"):
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO),
                        format="%(levelname)-8s|%(asctime)s|%(funcName)s:%(lineno)d| %(message)s",
                        datefmt="%H:%M:%S", force=True)
    return logging.getLogger("CTRLGEN")
log = logging.getLogger("CTRLGEN")
# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
THRESH              = 0.02       # ≤ 20 ms timestamp match
TIE_EPS             = 1e-3       # ≤ 1 mm counts as “same RMSE”
EXEC_FALLBACK       = float("inf")

def load_exec_time(run_root, stem):
    """
    Return mean (tracking) execution time for a run, or ∞ if unknown.
    Looks for files named either:
        <stem>_ExecMean.txt                (one float per line)
        <stem>_TrackingTimeStats.txt       (ms per frame, will avg)
    """
    cand1 = os.path.join(run_root, f"{stem}_ExecMean.txt")
    cand2 = os.path.join(run_root, f"{stem}_TrackingTimeStats.txt")
    try:
        if os.path.isfile(cand1):
            return float(open(cand1).read().strip().split()[0])
        if os.path.isfile(cand2):
            arr = np.loadtxt(cand2)
            return float(arr.mean())
    except Exception as e:
        log.debug("Exec-time parse failed for %s – %s", stem, e)
    return EXEC_FALLBACK

def load_tum_trajectory(path):
    if not os.path.isfile(path):
        log.warning("Missing trajectory: %s", path)
        return {}
    try:
        data = np.loadtxt(path, delimiter=" ")
        if data.ndim == 1:
            data = data.reshape(1, -1)
        return {row[0]: row[1:8] for row in data}
    except Exception as e:
        log.warning("Bad trajectory %s – %s", os.path.basename(path), e)
        return {}

pose_translation_error = lambda g, e: np.linalg.norm(g[0:3] - e[0:3])

def _dbg_candidates(t_gt, cand, best):
    """
    Pretty-print all (knob,val,err,exec) candidates that were inspected for
    a single ground-truth timestamp.  The one that gets chosen is flagged
    with a  ‘<==’  suffix so it’s easy to spot.
    """
    if not log.isEnabledFor(logging.DEBUG):      # avoid work if not needed
        return
    lines = [f"[{t_gt: .3f}] candidate set:"]
    for k, v, err, ex in cand:
        pick = " <==" if (k == best["key"] and v == best["val"]) else ""
        lines.append(f"  {k:>7}:{v:<3}   err={err:7.4f}   exec={ex:7.2f}{pick}")
    log.debug("\n".join(lines))

def parse_cfg(fname, seq):
    m = re.search(rf"{re.escape(seq)}_([a-zA-Z]+)_(\d+)\.txt", fname)
    return None if not m else (m.group(1), int(m.group(2)))
# ─────────────────────────────────────────────────────────────────────────────
def main(seq_path, ts_path_unused, gt_path, results_dir, ctrl_out, dataset, *,
         loglevel="INFO"):
    global log
    log = _init_logger(loglevel)
    stats = Counter(); per_skip = Counter()

    # ---------- Ground-truth -------------------------------------------------
    gt_raw = np.loadtxt(gt_path, delimiter=",", skiprows=1)
    ts     = gt_raw[:, 0]
    if ts.mean() > 1e12:                          # ns → s
        ts = ts * 1e-9
        log.debug("GT timestamps converted from ns to s")
    gt_poses = {t: np.array([px, py, pz, qx, qy, qz, qw])
                for t, px, py, pz, qw, qx, qy, qz in gt_raw}
    stats["gt"] = len(gt_poses)
    log.info("Loaded %d GT poses for %s", stats["gt"], dataset)

    # ---------- Gather trajectories -----------------------------------------
    base_stem  = f"{dataset}_default_0"
    base_file  = os.path.join(results_dir, f"{base_stem}.txt")
    base_traj  = load_tum_trajectory(base_file)
    base_exec  = load_exec_time(results_dir, base_stem)
    if not base_traj:
        log.error("Baseline missing – aborting")
        return 1

    alt = {}   # (knob,val) → {"traj":…, "exec":…}
    for fname in os.listdir(results_dir):
        if fname == os.path.basename(base_file) or not fname.endswith(".txt"):
            continue
        cfg = parse_cfg(fname, dataset)
        if not cfg:
            continue
        stem = fname[:-4]                        # strip ".txt"
        alt[cfg] = {"traj": load_tum_trajectory(os.path.join(results_dir, fname)),
                    "exec": load_exec_time(results_dir, stem)}

    stats["alt_runs"] = len(alt)
    log.info("Alt trajectories: %d", stats["alt_runs"])

    # ---------- Per-timestamp best selector ---------------------------------
    base_times = np.array(list(base_traj))
    best_for_ts = {}
    for t_gt, pose_gt in gt_poses.items():
        idx       = np.argmin(np.abs(base_times - t_gt))
        t_base    = base_times[idx]
        if abs(t_base - t_gt) > THRESH:
            per_skip["baseline_miss"] += 1
            continue
        best = {"key":"default", "val":0,
                "err":pose_translation_error(pose_gt, base_traj[t_base]),
                "exec":base_exec}
        base_err = pose_translation_error(pose_gt, base_traj[t_base])
        best = {"key":"default", "val":0,
                "err":base_err, "exec":base_exec}
        cand = [("default", 0, base_err, base_exec)]   # ← collect candidates
        # ---- check alts
        for (k,v), d in alt.items():
            traj = d["traj"]
            if not traj:
                per_skip["alt_empty"] += 1
                continue
            times = np.array(list(traj))
            t_alt = times[np.argmin(np.abs(times - t_gt))]
            if abs(t_alt - t_gt) > THRESH:
                per_skip["alt_miss"] += 1
                continue
            err  = pose_translation_error(pose_gt, traj[t_alt])
            if   err + TIE_EPS < best["err"]:
                best = {"key":k,"val":v,"err":err,"exec":d["exec"]}
            elif abs(err - best["err"]) <= TIE_EPS:         # tie on RMSE
                if d["exec"] < best["exec"]:
                    best = {"key":k,"val":v,"err":err,"exec":d["exec"]}
            # Always record what we looked at (even if trajectory was skipped)
            cand.append((k, v, err if traj else float("nan"), d["exec"]))
        best_for_ts[t_gt] = best
        _dbg_candidates(t_gt, cand, best)
        stats["eval"] += 1
        if best["key"] != "default":
            stats["improved"] += 1

    log.info("Eval %d GT poses (improved %d, skipped %d)",
             stats["eval"], stats["improved"], sum(per_skip.values()))

    # ── 4.  Emit control file  ───────────────────────────────────────────────
    os.makedirs(os.path.dirname(ctrl_out), exist_ok=True)
    default = dict(Skip_Frames=0, KP_max=200, KP_min=180, Processing_Frames=2)
    last    = default.copy(); written = 0

    with open(ctrl_out, "w") as f:
        for t in sorted(best_for_ts):
            op  = best_for_ts[t]          # {'key','val','err','exec'}
            tgt = last.copy()             # start from previous state

            if op["key"] == "skip":
                tgt["Skip_Frames"] = op["val"]
            elif op["key"] == "kp":
                tgt["KP_max"] = op["val"]
                tgt["KP_min"] = 54 if op["val"] == 60 else 180
            elif op["key"] == "mode":
                tgt["Processing_Frames"] = op["val"]

            # Only emit *one* line – the one for the chosen knob – if it changed.
            line_to_write = None
            if op["key"] == "skip" and tgt["Skip_Frames"] != last["Skip_Frames"]:
                line_to_write = f"{dataset},{t:.9f},Skip_Frames,{tgt['Skip_Frames']}"
            elif op["key"] == "kp"   and tgt["KP_max"]      != last["KP_max"]:
                line_to_write = f"{dataset},{t:.9f},KP_max,{tgt['KP_max']}"
            elif op["key"] == "mode" and tgt["Processing_Frames"] != last["Processing_Frames"]:
                line_to_write = f"{dataset},{t:.9f},Processing_Frames,{tgt['Processing_Frames']}"

            if line_to_write:
                f.write(line_to_write + "\n")
                written += 1
                last = tgt               # now the *whole* state is current
    log.info("Wrote %d commands → %s", written, ctrl_out)
    stats["cmds"] = written
    log.info("SUMMARY: %s", dict(stats))
    return 0
# ─────────────────────────────────────────────
def cli():
    ap = argparse.ArgumentParser(description="Generate control file with RMSE+ExecTime tie-break.")
    ap.add_argument("sequence_path"); ap.add_argument("timestamps_file")
    ap.add_argument("ground_truth_path"); ap.add_argument("results_dir")
    ap.add_argument("control_file_out");  ap.add_argument("dataset_name")
    ap.add_argument("--loglevel", default=os.getenv("SLAM_LOGLEVEL","INFO"))
    a = ap.parse_args()
    sys.exit(main(a.sequence_path, a.timestamps_file, a.ground_truth_path,
                  a.results_dir, a.control_file_out, a.dataset_name,
                  loglevel=a.loglevel))
if __name__ == "__main__":
    cli()
