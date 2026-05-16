import os
import glob
import json
import time
import argparse
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

def build_graph(frames_dir, fps):
    frame_files = sorted(glob.glob(os.path.join(frames_dir, "frame_*.png")))
    if not frame_files:
        return {"fps": fps, "n_frames": 0, "places": [], "edges": [], "latency_stats": {}}
        
    print("Loading local VLM (BLIP) for semantic state analysis...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)
    
    places = []
    edges = []
    
    current_place_id = 0
    representative_frame = 0
    
    places.append({
        "id": current_place_id,
        "representative_frame": 0,
        "frame_range": [0, 0]
    })
    
    print(f"Querying VLM for {len(frame_files)} frames (Batched)...")
    start_time = time.time()
    
    batch_size = 16
    all_captions = []
    
    for i in range(0, len(frame_files), batch_size):
        batch_files = frame_files[i:i+batch_size]
        images = [Image.open(f).convert("RGB") for f in batch_files]
        inputs = processor(images=images, return_tensors="pt", padding=True).to(device)
        out = model.generate(**inputs)
        captions = processor.batch_decode(out, skip_special_tokens=True)
        all_captions.extend(captions)
        
    rep_caption = all_captions[0]
    
    for i in range(1, len(frame_files)):
        curr_caption = all_captions[i]
        
        changed = (curr_caption != rep_caption)
        
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
            rep_caption = curr_caption
            
    duration = time.time() - start_time
    print(f"Real VLM baseline finished in {duration:.2f}s")
    
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
    parser.add_argument("--fps", type=float, default=15.0)
    args = parser.parse_args()
    
    graph = build_graph(args.frames_dir, args.fps)
    
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(graph, f, indent=2)
    print(f"Wrote VLM baseline graph with {len(graph['places'])} places to {args.out}")