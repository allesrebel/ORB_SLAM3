import json
import argparse
import os

def parse_ground_truth(action_log_path, fps=30):
    with open(action_log_path, 'r') as f:
        data = json.load(f)
    
    actions = data.get('action_log', [])
    
    # We consider significant actions as triggering a new state.
    # Significant: CLICK, DBLCLICK, KEY_PRESS, SCROLL
    state_frames = [0] # Frame 0 is State 0
    
    for action in actions:
        atype = action.get('action_type', '')
        
        if atype in ['CLICK', 'DBLCLICK', 'KEY_PRESS', 'SCROLL']:
            params = action.get('action_params', {})
            # Stricter filtering: Ensure CLICK has a semantic target (text) or a known UI component (groundcua_id)
            if atype in ['CLICK', 'DBLCLICK'] and not params.get('text') and not action.get('groundcua_id'):
                continue
                
            ts = action.get('timestamp', 0.0)
            frame_idx = int(ts * fps)
            
            # Debounce rapid actions
            if len(state_frames) == 0 or frame_idx > state_frames[-1] + int(fps * 0.5):
                state_frames.append(frame_idx)
                
    places = []
    edges = []
    
    for i, start_f in enumerate(state_frames):
        end_f = state_frames[i+1] - 1 if i+1 < len(state_frames) else start_f + int(fps * 10)
        places.append({
            "id": i,
            "representative_frame": start_f,
            "frame_range": [start_f, end_f]
        })
        if i > 0:
            edges.append({
                "from": i - 1,
                "to": i,
                "frame": start_f,
                "type": "new"
            })
            
    return {"fps": fps, "n_frames": places[-1]["frame_range"][1] + 1, "places": places, "edges": edges}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action-log", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args()
    
    gt_graph = parse_ground_truth(args.action_log, args.fps)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(gt_graph, f, indent=2)
    print(f"Wrote GT graph with {len(gt_graph['places'])} places to {args.out}")
