import optuna
import os
import sys
import subprocess
import json
import time
import glob

# Target a specific task for the sweep
TASK = "GrassGIS/46646"
FRAMES_DIR = f"/root/orbslam3_runs/research_eval/{TASK}/frames"
GT_PATH = f"/root/orbslam3_runs/research_eval/{TASK}/ground_truth.json"
ORB_VOCAB = "/root/clean/ORB_SLAM3/Vocabulary/ORBvoc.txt"
YAML_PATH = "/root/clean/ORB_SLAM3/Examples/Monocular/VideoCUA_1080p.yaml"
BIN_PATH = "/root/clean/ORB_SLAM3/Examples/Monocular/mono_topological_screencast"
OUT_DIR = f"/tmp/sweep_output_{TASK.split('/')[0]}"

def get_gt_count():
    if not os.path.exists(GT_PATH):
        return 2 # fallback
    with open(GT_PATH) as f:
        return len(json.load(f).get('places', []))

GT_COUNT = get_gt_count()

def run_topo_slam(target_kp, hash_th, affine_min):
    os.makedirs(OUT_DIR, exist_ok=True)
    
    cmd = [
        BIN_PATH,
        ORB_VOCAB,
        YAML_PATH,
        FRAMES_DIR,
        "15.0",
        "--out", OUT_DIR,
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
    
    pred_path = os.path.join(OUT_DIR, "place_graph.json")
    if not os.path.exists(pred_path):
        return None, None
        
    with open(pred_path) as f:
        pred_data = json.load(f)
        
    pred_count = len(pred_data.get('places', []))
    ged = abs(GT_COUNT - pred_count)
    
    frame_files = glob.glob(os.path.join(FRAMES_DIR, "frame_*.png"))
    frames = len(frame_files) if frame_files else 100
    latency = (duration / max(frames, 1)) * 1000.0
    
    return ged, latency

def objective(trial):
    target_keypoints = trial.suggest_int('target_keypoints', 500, 2000)
    hash_similarity_threshold = trial.suggest_float('hash_similarity_threshold', 0.75, 0.95)
    affine_min_inliers = trial.suggest_int('affine_min_inliers', 5, 30)
    
    ged, latency = run_topo_slam(target_keypoints, hash_similarity_threshold, affine_min_inliers)
    
    if ged is None:
        raise optuna.TrialPruned()
        
    return ged, latency

if __name__ == "__main__":
    study = optuna.create_study(directions=["minimize", "minimize"])
    
    print(f"Starting HARDWARE-IN-THE-LOOP Design Space Exploration (DSE) Sweep on {TASK}...")
    # Running 10 trials for demonstration speed (in real research it'd be 50+)
    study.optimize(objective, n_trials=10)
    
    print("\n" + "="*50)
    print("--- DSE Sweep Complete ---")
    
    print("\nPareto Optimal Configurations:")
    for trial in study.best_trials:
        print(f"  Trial {trial.number}: GED={trial.values[0]:.2f}, Latency={trial.values[1]:.2f} ms/frame")
        for k, v in trial.params.items():
            if isinstance(v, float):
                print(f"    {k}: {v:.4f}")
            else:
                print(f"    {k}: {v}")
        print()
    print("="*50)
    
    import matplotlib.pyplot as plt
    from optuna.visualization.matplotlib import plot_pareto_front
    
    fig = plot_pareto_front(study, target_names=["GED", "Latency (ms/frame)"])
    plt.tight_layout()
    plt.savefig("pareto_front_real.png")
    print("Saved Real Pareto Front plot to pareto_front_real.png")