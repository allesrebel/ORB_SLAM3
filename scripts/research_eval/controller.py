import cv2
import numpy as np
import argparse
import glob
import os
import time

def compute_chaos_score(prev_gray, curr_gray):
    """
    Computes a simple 'Chaos Score' representing the fraction of the screen
    that has significantly changed.
    """
    # Absolute difference between frames
    diff = cv2.absdiff(prev_gray, curr_gray)
    # Thresholding to ignore minor compression artifacts or video noise
    _, thresh = cv2.threshold(diff, 15, 255, cv2.THRESH_BINARY)
    # The score is the percentage of pixels that changed significantly
    score = np.sum(thresh) / 255.0 / (thresh.shape[0] * thresh.shape[1])
    return score

def run_controller(frames_dir, chaos_threshold=0.01, cooldown_frames=5):
    """
    Simulates the Reflex Layer's chaos gating.
    """
    frame_files = sorted(glob.glob(os.path.join(frames_dir, "frame_*.png")))
    if not frame_files:
        print("No frames found in:", frames_dir)
        return

    prev_gray = None
    chaos_history = []
    stable_frames_count = 0
    state_id = 0
    vlm_triggers = 0
    
    print(f"--- Controller Starting: Processing {len(frame_files)} frames ---")
    start_time = time.time()
    
    for idx, fpath in enumerate(frame_files):
        img = cv2.imread(fpath)
        if img is None:
            continue
        
        curr_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        if prev_gray is None:
            prev_gray = curr_gray
            print(f"[Frame {idx:05d}] INIT - Baseline State {state_id}")
            continue
            
        chaos_score = compute_chaos_score(prev_gray, curr_gray)
        chaos_history.append(chaos_score)
        
        if chaos_score > chaos_threshold:
            # High chaos: UI is moving (Scrolling, animating, typing fast)
            # Action: Suppress VLM, rely on SLAM to track motion.
            stable_frames_count = 0
            if idx % 10 == 0: # Print occasionally to avoid spam
                print(f"[Frame {idx:05d}] CHAOS ({chaos_score:.3f}) - Suppressing VLM")
        else:
            # Low chaos: UI is stable
            stable_frames_count += 1
            
            # If the UI has been stable for exactly 'cooldown_frames', trigger the Cognitive Layer.
            if stable_frames_count == cooldown_frames:
                state_id += 1
                vlm_triggers += 1
                print(f"[Frame {idx:05d}] STABLE ({chaos_score:.3f}) -> TRIGGERING VLM (State {state_id})")
                
        prev_gray = curr_gray

    duration = time.time() - start_time
    print("-" * 50)
    print(f"Controller Summary:")
    print(f"Total Frames:   {len(frame_files)}")
    print(f"VLM Triggers:   {vlm_triggers} (Filtered out {len(frame_files) - vlm_triggers} redundant frames)")
    print(f"Avg Latency:    {(duration/len(frame_files))*1000:.2f} ms/frame")
    print("-" * 50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames-dir", required=True, help="Path to directory containing sequential frame_XXXXX.png")
    parser.add_argument("--chaos-threshold", type=float, default=0.005, help="Percentage of screen change to define 'chaos'")
    parser.add_argument("--cooldown", type=int, default=5, help="Frames of stability required to trigger VLM")
    args = parser.parse_args()
    
    run_controller(args.frames_dir, args.chaos_threshold, args.cooldown)
