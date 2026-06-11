"""
Pixel Frame Differencing (MAE) baseline.

For each frame, computes normalized MAE against the representative frame of the
active state. A transition is triggered when (1 - normalized_MAE) < threshold.

Interface mirrors ssim_baseline.py. Output file: pixeldiff_graph.json
"""
import os
import glob
import json
import time
import argparse
import numpy as np
import cv2


def normalized_mae(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """Mean Absolute Error normalized to [0,1] (divide by 255)."""
    return float(np.mean(np.abs(img_a.astype(np.float32) - img_b.astype(np.float32))) / 255.0)


def build_graph(frames_dir: str, threshold: float, fps: float) -> dict:
    """
    Build a place graph using pixel MAE similarity.

    similarity = 1 - normalized_MAE(current_frame, representative_frame)
    Transition triggered when similarity < threshold.
    """
    frame_files = sorted(glob.glob(os.path.join(frames_dir, "frame_*.png")))
    if not frame_files:
        return {"fps": fps, "n_frames": 0, "places": [], "edges": [], "latency_stats": {}}

    places = []
    edges = []

    current_place_id = 0
    representative_frame = 0

    places.append({
        "id": current_place_id,
        "representative_frame": 0,
        "frame_range": [0, 0]
    })

    print(f"Computing Pixel Diff (MAE) for {len(frame_files)} frames (threshold={threshold:.4f})...")
    start_time = time.time()

    rep_img = cv2.imread(frame_files[0], cv2.IMREAD_GRAYSCALE)

    for i in range(1, len(frame_files)):
        curr_img = cv2.imread(frame_files[i], cv2.IMREAD_GRAYSCALE)
        mae = normalized_mae(rep_img, curr_img)
        similarity = 1.0 - mae

        if similarity >= threshold:
            places[current_place_id]["frame_range"][1] = i
        else:
            new_id = current_place_id + 1
            places.append({
                "id": new_id,
                "representative_frame": i,
                "frame_range": [i, i]
            })
            edges.append({
                "from": current_place_id,
                "to": new_id,
                "frame": i,
                "type": "new"
            })
            current_place_id = new_id
            representative_frame = i
            rep_img = cv2.imread(frame_files[representative_frame], cv2.IMREAD_GRAYSCALE)

    duration = time.time() - start_time
    print(f"Pixel Diff baseline finished in {duration:.2f}s — {len(places)} places")

    graph = {
        "fps": fps,
        "n_frames": len(frame_files),
        "places": places,
        "edges": edges,
        "latency_stats": {
            "total_time_s": duration,
            "ms_per_frame": (duration / len(frame_files)) * 1000 if frame_files else 0,
            "fps": len(frame_files) / duration if duration > 0 else 0
        }
    }
    return graph


# ---------------------------------------------------------------------------
# Threshold search (same strategy as ssim/embedding)
# ---------------------------------------------------------------------------

def search_threshold(runs_dir: str, candidate_thresholds=None) -> float:
    """
    Grid-search the threshold that minimises mean temporal_edit_cost across
    all tasks that already have a ground_truth.json.
    """
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from eval_harness import evaluate_graph

    if candidate_thresholds is None:
        candidate_thresholds = [round(v, 3) for v in list(
            # range from 0.70 to 0.99 in steps of 0.01
            [0.70 + i * 0.01 for i in range(30)]
        )]

    gt_files = glob.glob(os.path.join(runs_dir, "**", "ground_truth.json"), recursive=True)
    if not gt_files:
        print("No ground truth files found — using default threshold 0.92")
        return 0.92

    best_threshold = 0.92
    best_cost = float("inf")

    for th in candidate_thresholds:
        costs = []
        for gt_path in gt_files:
            task_dir = os.path.dirname(gt_path)
            frames_dir = os.path.join(task_dir, "frames")
            if not os.path.isdir(frames_dir):
                continue
            graph = build_graph(frames_dir, th, 15.0)
            # Write to a temp location for evaluate_graph
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
                tmp_path = tf.name
                json.dump(graph, tf)
            metrics = evaluate_graph(gt_path, tmp_path)
            os.unlink(tmp_path)
            if metrics:
                costs.append(metrics["temporal_edit_cost"])
        if costs:
            mean_cost = float(np.mean(costs))
            print(f"  threshold={th:.3f}  mean_TSEC={mean_cost:.4f}")
            if mean_cost < best_cost:
                best_cost = mean_cost
                best_threshold = th

    print(f"Best threshold: {best_threshold:.3f}  (mean_TSEC={best_cost:.4f})")
    return best_threshold


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pixel Diff (MAE) baseline — mirrors ssim_baseline.py interface"
    )
    parser.add_argument("--frames-dir", required=True, help="Directory of frame_XXXXX.png files")
    parser.add_argument("--out", required=True, help="Output JSON path (e.g. pixeldiff_graph.json)")
    parser.add_argument("--threshold", type=float, default=0.92,
                        help="Similarity threshold (1 - norm_MAE); transition when below this")
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument(
        "--search-threshold", metavar="RUNS_DIR",
        help="If provided, grid-search the best threshold over all tasks in RUNS_DIR first"
    )
    args = parser.parse_args()

    threshold = args.threshold
    if args.search_threshold:
        print("Running threshold search...")
        threshold = search_threshold(args.search_threshold)
        print(f"Using optimised threshold: {threshold:.4f}")

    graph = build_graph(args.frames_dir, threshold, args.fps)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(graph, f, indent=2)
    print(f"Wrote Pixel Diff baseline graph with {len(graph['places'])} places to {args.out}")
