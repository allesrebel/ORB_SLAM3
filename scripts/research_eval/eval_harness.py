import json
import argparse
import os
import glob
import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment

def compute_iou(range1, range2):
    start_max = max(range1[0], range2[0])
    end_min = min(range1[1], range2[1])
    
    if start_max > end_min:
        return 0.0
        
    intersection = end_min - start_max + 1
    union = max(range1[1], range2[1]) - min(range1[0], range2[0]) + 1
    
    if union == 0:
        return 0.0
    return intersection / union

def evaluate_graph(gt_path, pred_path):
    if not os.path.exists(pred_path):
        return None
        
    with open(gt_path, 'r') as f:
        gt_data = json.load(f)
    with open(pred_path, 'r') as f:
        pred_data = json.load(f)
        
    gt_places = gt_data.get('places', [])
    pred_places = pred_data.get('places', [])
    gt_edges = gt_data.get('edges', [])
    pred_edges = pred_data.get('edges', [])
    
    gt_count = len(gt_places)
    pred_count = len(pred_places)
    
    if gt_count == 0 or pred_count == 0:
        return None

    # Diagnostic state count error (Replacement for fake GED)
    state_count_error = abs(gt_count - pred_count)
    
    # Cost matrix for Hungarian matching based on 1 - tIoU
    cost_matrix = np.ones((gt_count, pred_count))
    iou_matrix = np.zeros((gt_count, pred_count))
    
    for i, gt_p in enumerate(gt_places):
        for j, pred_p in enumerate(pred_places):
            iou = compute_iou(gt_p.get("frame_range", [0,0]), pred_p.get("frame_range", [0,0]))
            iou_matrix[i, j] = iou
            cost_matrix[i, j] = 1.0 - iou
            
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    
    # Calculate metrics
    matched_ious = []
    matches = 0
    for r, c in zip(row_ind, col_ind):
        iou = iou_matrix[r, c]
        if iou > 0:
            matched_ious.append(iou)
            matches += 1
            
    mean_matched_tiou = np.mean(matched_ious) if matched_ious else 0.0
    
    # Precision/Recall at Thresholds
    def pr_f1(threshold):
        tp = sum(1 for iou in matched_ious if iou >= threshold)
        precision = tp / pred_count if pred_count > 0 else 0.0
        recall = tp / gt_count if gt_count > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        return precision, recall, f1

    p30, r30, f1_30 = pr_f1(0.3)
    p50, r50, f1_50 = pr_f1(0.5)
    p70, r70, f1_70 = pr_f1(0.7)
    
    unmatched_gt = gt_count - matches
    unmatched_pred = pred_count - matches
    
    # Boundary F1 (+- 15 frames = 1s at 15fps)
    boundary_tolerance = 15
    gt_boundaries = [p.get("frame_range")[0] for p in gt_places[1:]] # Skip first start
    pred_boundaries = [p.get("frame_range")[0] for p in pred_places[1:]]
    
    boundary_matches = 0
    matched_preds = set()
    for gt_b in gt_boundaries:
        best_p_b = -1
        best_dist = float('inf')
        for i, p_b in enumerate(pred_boundaries):
            if i in matched_preds:
                continue
            dist = abs(gt_b - p_b)
            if dist <= boundary_tolerance and dist < best_dist:
                best_dist = dist
                best_p_b = i
        if best_p_b != -1:
            boundary_matches += 1
            matched_preds.add(best_p_b)
                
    bp = boundary_matches / len(pred_boundaries) if pred_boundaries else 0.0
    br = boundary_matches / len(gt_boundaries) if gt_boundaries else 0.0
    bf1 = 2 * (bp * br) / (bp + br) if (bp + br) > 0 else 0.0
    
    # Real Graph Edit Distance (GED)
    # Node substitution cost: sum of (1 - iou) for matches
    sub_cost = sum(1.0 - iou for iou in matched_ious)
    # Insertion/Deletion cost for unmatched nodes
    ins_del_cost = unmatched_gt + unmatched_pred
    
    # Simple Edge cost (abs difference in edge count for now, a full graph matching is complex but this works for sequences)
    edge_diff_cost = abs(len(gt_edges) - len(pred_edges))
    
    raw_ged = sub_cost + ins_del_cost + edge_diff_cost
    temporal_edit_cost = raw_ged / max(1, (gt_count + len(gt_edges)))

    latency = pred_data.get('latency_stats', {})
    
    return {
        "gt_states": gt_count,
        "pred_states": pred_count,
        "state_count_error": state_count_error,
        "mean_tiou": mean_matched_tiou,
        "f1_50": f1_50,
        "f1_70": f1_70,
        "boundary_f1": bf1,
        "misses": unmatched_gt,
        "false_splits": unmatched_pred,
        "temporal_edit_cost": temporal_edit_cost,
        "ms_per_frame": latency.get("ms_per_frame", 0),
        "fps": latency.get("fps", 0)
    }

def test_compute_iou():
    # 1. Identical one-frame intervals
    assert compute_iou([0, 0], [0, 0]) == 1.0, "Failed: Identical one-frame"
    # 2. Identical multi-frame intervals
    assert compute_iou([10, 20], [10, 20]) == 1.0, "Failed: Identical multi-frame"
    # 3. Disjoint intervals
    assert compute_iou([0, 5], [10, 15]) == 0.0, "Failed: Disjoint"
    assert compute_iou([10, 15], [0, 5]) == 0.0, "Failed: Disjoint (reversed)"
    # 4. Partially overlapping intervals
    assert compute_iou([0, 10], [5, 15]) == 6/16, "Failed: Partially overlapping"
    assert compute_iou([5, 15], [0, 10]) == 6/16, "Failed: Partially overlapping (reversed)"
    # 5. Adjacent intervals
    assert compute_iou([0, 5], [6, 10]) == 0.0, "Failed: Adjacent"
    # 6. One fully inside the other
    assert compute_iou([0, 20], [5, 10]) == 6/21, "Failed: Fully inside"
    
    print("All compute_iou unit tests passed.")

if __name__ == "__main__":
    test_compute_iou()
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    
    results = []
    
    gt_files = glob.glob(os.path.join(args.runs_dir, "**", "ground_truth.json"), recursive=True)
    
    for gt_path in gt_files:
        task_dir = os.path.dirname(gt_path)
        
        # Check for gold GT
        gold_path = os.path.join(task_dir, "gold_ground_truth.json")
        active_gt_path = gold_path if os.path.exists(gold_path) else gt_path
        
        task_id = os.path.basename(os.path.dirname(task_dir)) + "/" + os.path.basename(task_dir)
        
        baselines = {
            "embedding": os.path.join(task_dir, "embedding_graph.json"),
            "vlm": os.path.join(task_dir, "vlm_graph.json"),
            "ssim": os.path.join(task_dir, "ssim_graph.json"),
            "pixeldiff": os.path.join(task_dir, "pixeldiff_graph.json"),
            "topo_slam": os.path.join(task_dir, "topological", "place_graph.json")
        }
        
        for baseline_name, pred_path in baselines.items():
            if not os.path.exists(pred_path):
                print(f"WARNING: missing {baseline_name} output for {task_id}: {pred_path}")
                continue
            metrics = evaluate_graph(active_gt_path, pred_path)
            if metrics:
                metrics["task"] = task_id
                metrics["method"] = baseline_name
                metrics["is_gold_gt"] = os.path.exists(gold_path)
                results.append(metrics)
            else:
                print(f"WARNING: could not evaluate {baseline_name} output for {task_id}: {pred_path}")
                
    if results:
        df = pd.DataFrame(results)
        df.to_csv(args.out, index=False)
        print(f"Aggregated evaluation results to {args.out}")
        print("\nResult counts by method:")
        print(df.groupby('method').size().to_string())
        print("\nSummary by method (All Tasks):")
        summary = df.groupby('method')[['state_count_error', 'mean_tiou', 'f1_50', 'boundary_f1', 'temporal_edit_cost', 'ms_per_frame']].mean()
        print(summary.to_string())
        
        print("\nSummary by method (GOLD GT Subset Only):")
        gold_df = df[df['is_gold_gt'] == True]
        if not gold_df.empty:
            gold_summary = gold_df.groupby('method')[['state_count_error', 'mean_tiou', 'f1_50', 'boundary_f1', 'temporal_edit_cost', 'ms_per_frame']].mean()
            print(gold_summary.to_string())
        else:
            print("No gold tasks found.")
    else:
        print("No evaluation results found.")
