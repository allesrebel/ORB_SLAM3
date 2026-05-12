import os
import glob
import json
import time
import argparse
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPVisionModelWithProjection

def compute_embeddings(frames_dir, device='cpu'):
    print(f"Loading CLIP model to {device}...")
    model = CLIPVisionModelWithProjection.from_pretrained("openai/clip-vit-base-patch32").to(device)
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    
    frame_files = sorted(glob.glob(os.path.join(frames_dir, "frame_*.png")))
    embeddings = []
    
    print(f"Computing embeddings for {len(frame_files)} frames...")
    start = time.time()
    
    # Process in batches to speed it up
    batch_size = 16
    for i in range(0, len(frame_files), batch_size):
        batch_files = frame_files[i:i+batch_size]
        images = [Image.open(f).convert("RGB") for f in batch_files]
        inputs = processor(images=images, return_tensors="pt").to(device)
        with torch.no_grad():
            emb = model(**inputs).image_embeds
            emb = emb / emb.norm(p=2, dim=-1, keepdim=True)
            embeddings.extend(emb.cpu().unbind(0))
            
    end = time.time()
    
    print(f"Computed {len(embeddings)} embeddings in {end - start:.2f}s")
    return embeddings, end - start, frame_files

def build_graph(embeddings, threshold, fps):
    if not embeddings:
        return {"fps": fps, "n_frames": 0, "places": [], "edges": []}
        
    places = []
    edges = []
    
    current_place_id = 0
    representative_emb = embeddings[0].unsqueeze(0)
    
    places.append({
        "id": current_place_id,
        "representative_frame": 0,
        "frame_range": [0, 0]
    })
    
    for i in range(1, len(embeddings)):
        emb_i = embeddings[i].unsqueeze(0)
        sim = torch.nn.functional.cosine_similarity(representative_emb, emb_i)[0].item()
        
        if sim >= threshold:
            places[current_place_id]["frame_range"][1] = i
        else:
            # new place
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
            representative_emb = emb_i
            
    return {"fps": fps, "n_frames": len(embeddings), "places": places, "edges": edges}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--threshold", type=float, default=0.98) # High threshold for CLIP
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()
    
    embeddings, duration, frame_files = compute_embeddings(args.frames_dir, args.device)
    graph = build_graph(embeddings, args.threshold, args.fps)
    
    # Inject latency stats
    graph["latency_stats"] = {
        "total_time_s": duration,
        "ms_per_frame": (duration / len(embeddings)) * 1000 if embeddings else 0,
        "fps": len(embeddings) / duration if duration > 0 else 0
    }
    
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(graph, f, indent=2)
    print(f"Wrote Embedding baseline graph with {len(graph['places'])} places to {args.out}")
