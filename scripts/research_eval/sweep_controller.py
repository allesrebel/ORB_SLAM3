import optuna
import os
import sys
import subprocess
import json
import time
import glob
import numpy as np
from eval_harness import evaluate_graph

# Target tasks for the sweep
TASKS = ["GrassGIS/46646", "OnlyOffice_Forms/41765", "Conky/106644"]
ORB_VOCAB = "/root/clean/ORB_SLAM3/Vocabulary/ORBvoc.txt"
YAML_PATH = "/root/clean/ORB_SLAM3/Examples/Monocular/VideoCUA_1080p.yaml"
BIN_PATH = "/root/clean/ORB_SLAM3/Examples/Monocular/mono_topological_screencast"

def run_topo_slam(task, target_kp, hash_th, affine_min):
    frames_dir = f"/root/orbslam3_runs/research_eval/{task}/frames"
    gt_path = f"/root/orbslam3_runs/research_eval/{task}/ground_truth.json"
    out_dir = f"/tmp/sweep_output_{task.replace('/', '_')}"
    os.makedirs(out_dir, exist_ok=True)
    
    cmd = [
        BIN_PATH,
        ORB_VOCAB,
        YAML_PATH,
        frames_dir,
        "15.0",
        "--out", out_dir,
        "--target_kp", str(target_kp),
        "--hash_th", str(hash_th),
        "--affine_min", str(affine_min)
    ]
    
    start = time.time()
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None, None
        
    duration = time.time() - start
    
    pred_path = os.path.join(out_dir, "place_graph.json")
    if not os.path.exists(pred_path):
        return None, None
        
    metrics = evaluate_graph(gt_path, pred_path)
    if not metrics:
        return None, None
        
    temporal_edit_cost = metrics["temporal_edit_cost"]
    
    frame_files = glob.glob(os.path.join(frames_dir, "frame_*.png"))
    frames = len(frame_files) if frame_files else 100
    latency = (duration / max(frames, 1)) * 1000.0
    
    return temporal_edit_cost, latency

def objective(trial):
    target_keypoints = trial.suggest_int('target_keypoints', 500, 2000)
    hash_similarity_threshold = trial.suggest_float('hash_similarity_threshold', 0.75, 0.95)
    affine_min_inliers = trial.suggest_int('affine_min_inliers', 5, 30)
    
    total_cost = 0
    total_latency = 0
    valid_tasks = 0
    
    for task in TASKS:
        cost, latency = run_topo_slam(task, target_keypoints, hash_similarity_threshold, affine_min_inliers)
        if cost is not None:
            total_cost += cost
            total_latency += latency
            valid_tasks += 1
            
    if valid_tasks == 0:
        raise optuna.TrialPruned()
        
    return total_cost / valid_tasks, total_latency / valid_tasks

if __name__ == "__main__":
    study = optuna.create_study(directions=["minimize", "minimize"])
    
    print(f"Starting HARDWARE-IN-THE-LOOP Design Space Exploration (DSE) Sweep on {len(TASKS)} tasks...")
    # Run full 50 trials
    study.optimize(objective, n_trials=50)
    
    print("\n" + "="*50)
    print("--- DSE Sweep Complete ---")
    
    print("\nPareto Optimal Configurations:")
    for trial in study.best_trials:
        print(f"  Trial {trial.number}: Temporal Edit Cost={trial.values[0]:.4f}, Latency={trial.values[1]:.2f} ms/frame")
        for k, v in trial.params.items():
            if isinstance(v, float):
                print(f"    {k}: {v:.4f}")
            else:
                print(f"    {k}: {v}")
        print()
    print("="*50)
    
    import matplotlib.pyplot as plt
    from optuna.visualization.matplotlib import plot_pareto_front
    
    fig = plot_pareto_front(study, target_names=["Temporal Edit Cost", "Latency (ms/frame)"])
    plt.tight_layout()
    plt.savefig("pareto_front_real.png")
    print("Saved Real Pareto Front plot to pareto_front_real.png")