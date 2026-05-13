import json
import argparse
import os
import glob
import pandas as pd

def compute_ged(gt_places, pred_places):
    """
    Simplified Graph Edit Distance or alignment error based on sequence of states.
    For sequential video state graphs, this can be approximated as the edit distance 
    (Levenshtein distance) between the sequence of states. Since we don't have perfect
    matching without visual feature tracking, we use absolute length difference as a proxy
    for over/under-segmentation.
    """
    return abs(len(gt_places) - len(pred_places))

def evaluate_graph(gt_path, pred_path):
    if not os.path.exists(pred_path):
        return None
        
    with open(gt_path, 'r') as f:
        gt_data = json.load(f)
    with open(pred_path, 'r') as f:
        pred_data = json.load(f)
        
    gt_places = gt_data.get('places', [])
    pred_places = pred_data.get('places', [])
    
    gt_count = len(gt_places)
    pred_count = len(pred_places)
    ratio = pred_count / gt_count if gt_count > 0 else 0
    ged = compute_ged(gt_places, pred_places)
    latency = pred_data.get('latency_stats', {})
    
    return {
        "gt_states": gt_count,
        "pred_states": pred_count,
        "ratio": ratio,
        "ged": ged,
        "ms_per_frame": latency.get("ms_per_frame", 0),
        "fps": latency.get("fps", 0)
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", required=True, help="Directory containing task evaluation outputs")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()
    
    results = []
    
    # Find all ground truth files
    gt_files = glob.glob(os.path.join(args.runs_dir, "**", "ground_truth.json"), recursive=True)
    
    for gt_path in gt_files:
        task_dir = os.path.dirname(gt_path)
        task_id = os.path.basename(os.path.dirname(task_dir)) + "/" + os.path.basename(task_dir)
        
        # Check for baselines
        baselines = {
            "embedding": os.path.join(task_dir, "embedding_graph.json"),
            "vlm": os.path.join(task_dir, "vlm_graph.json"),
            "ssim": os.path.join(task_dir, "ssim_graph.json"),
            "topo_slam": os.path.join(task_dir, "topological", "place_graph.json") # From Topo-SLAM output
        }
        
        for baseline_name, pred_path in baselines.items():
            metrics = evaluate_graph(gt_path, pred_path)
            if metrics:
                metrics["task"] = task_id
                metrics["method"] = baseline_name
                results.append(metrics)
                
    if results:
        df = pd.DataFrame(results)
        df.to_csv(args.out, index=False)
        print(f"Aggregated evaluation results to {args.out}")
        print("\nSummary by method:")
        print(df.groupby('method')[['ratio', 'ged', 'ms_per_frame', 'fps']].mean())
    else:
        print("No evaluation results found.")
