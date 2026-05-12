import os
import glob
import json
import time
import argparse
import random

def query_vlm_mock(frame1_path, frame2_path):
    """
    Dummy mock function to simulate VLM latency and occasional state changes.
    In a real scenario, this would call GPT-4V or Claude 3.5 Sonnet API with:
    'Are these two UI frames showing the same functional state? Answer YES or NO.'
    """
    time.sleep(0.1) # Simulate some network latency
    # Randomly change state with 5% probability for the sake of generating a dummy graph
    return random.random() < 0.05

def build_graph(frames_dir, fps):
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
    
    print(f"Querying VLM for {len(frame_files)} frames...")
    start_time = time.time()
    
    # We step through frames. In reality, one might sub-sample to save VLM costs.
    # For this baseline, we evaluate every frame to get accurate temporal boundaries.
    for i in range(1, len(frame_files)):
        changed = query_vlm_mock(frame_files[representative_frame], frame_files[i])
        
        if not changed:
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
    print(f"VLM baseline finished in {duration:.2f}s")
    
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
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args()
    
    graph = build_graph(args.frames_dir, args.fps)
    
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(graph, f, indent=2)
    print(f"Wrote VLM baseline graph with {len(graph['places'])} places to {args.out}")
