import os
import glob
import json
import time
import argparse
import cv2
from skimage.metrics import structural_similarity as ssim

def build_graph(frames_dir, threshold, fps):
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
    
    print(f"Computing SSIM for {len(frame_files)} frames...")
    start_time = time.time()
    
    prev_img = cv2.imread(frame_files[0], cv2.IMREAD_GRAYSCALE)
    
    for i in range(1, len(frame_files)):
        curr_img = cv2.imread(frame_files[i], cv2.IMREAD_GRAYSCALE)
        
        rep_img = cv2.imread(frame_files[representative_frame], cv2.IMREAD_GRAYSCALE)
        score, _ = ssim(rep_img, curr_img, full=True)
        
        if score >= threshold:
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
            
    duration = time.time() - start_time
    print(f"SSIM baseline finished in {duration:.2f}s")
    
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--threshold", type=float, default=0.95)
    parser.add_argument("--fps", type=float, default=15.0)
    args = parser.parse_args()
    
    graph = build_graph(args.frames_dir, args.threshold, args.fps)
    
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(graph, f, indent=2)
    print(f"Wrote SSIM baseline graph with {len(graph['places'])} places to {args.out}")
