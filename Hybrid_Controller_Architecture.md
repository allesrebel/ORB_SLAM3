# Adaptive Controller Architecture for Hybrid VLM-SLAM Systems

## 1. Motivation
Hardcoding SLAM parameters (e.g., `minThFAST=2` or a strict temporal threshold) works well for specific evaluation sequences but fails to generalize across the vast diversity of digital UIs. A dense, text-heavy IDE requires different feature extraction logic than a minimalist, white-space-heavy PDF viewer. Furthermore, relying purely on either fast SLAM (which lacks semantic understanding) or slow VLMs (which suffer from >1s latency and high API costs) creates a fragile system. 

To solve this, we propose an **Adaptive Edge Controller**—a closed-loop supervisor that dynamically routes frames between a fast "Reflex" layer (Topo-SLAM) and a slow "Cognitive" layer (VLM) while continuously tuning SLAM extraction parameters based on visual chaos.

---

## 2. Core Architectural Components

### A. The Reflex Layer (Topo-SLAM)
*   **Role:** High-speed (15-30 FPS) tracking and temporal filtering.
*   **Mechanism:** Runs continuously on the CPU edge. Tracks low-level visual continuity using dynamic FAST grids, Affine verification, and Pixel Hashing.
*   **Output:** Generates a stream of "chaos" metrics (feature count, tracking speed, RANSAC inliers) and signals state boundaries when the UI is stable.

### B. The Cognitive Layer (Vision-Language Model)
*   **Role:** Deep semantic reasoning and state understanding.
*   **Mechanism:** Triggered only on highly stable, representative keyframes. Uses models like GPT-4o, Claude 3.5, or edge-optimized Qwen-VL.
*   **Output:** Determines if the functional layout has changed semantically, reads text, and provides corrective feedback if the Reflex layer falsely merged two distinct states.

### C. The Adaptive Controller (Supervisor)
*   **Role:** The "Brain Stem." Sits between the video stream, the Reflex layer, and the Cognitive layer. Modulates parameters in real-time.

---

## 3. Dynamic Controller Mechanisms

### 3.1. Chaos Gating (Motion/Variance Detection)
The Controller calculates a rapid "Chaos Score" per frame (using simple inter-frame MSE, optical flow, or just Topo-SLAM's tracking loss).
*   **High Chaos (Scrolling, dragging, animations):** The Controller heavily suppresses VLM calls (cost-saving) and drops the SLAM similarity thresholds (tolerating blur and movement).
*   **Low Chaos (Stable UI):** The Controller triggers a VLM call on the finalized state, signaling the semantic layer to "read the room."

### 3.2. Adaptive Feature Target (PID Control)
Instead of hardcoding `iniThFAST` and `minThFAST`, the Controller implements a PID (Proportional-Integral-Derivative) loop targeting a fixed number of keypoints (e.g., 1000 KPs).
*   *If KPs < 500 (Blank UI):* Controller exponentially decays `minThFAST` toward 1 and enables heavy image-enhancement to force feature detection on flat panels.
*   *If KPs > 2500 (Dense Text UI):* Controller raises the threshold to prevent the SLAM matching layer from lagging out due to overwhelming noise.

### 3.3. Semantic Feedback Loop
If the Cognitive Layer (VLM) determines that two states are functionally different despite Topo-SLAM claiming they are identical (a false positive), the Controller receives a penalty signal. It dynamically tightens the RANSAC inlier threshold or increases the Pixel Hash strictness (e.g., jumping from `0.85` to `0.92`) to prevent further false merges.

---

## 4. Implementation Plan

**Phase 1: Controller Intercept Module**
*   Build a Python daemon (`controller.py`) that acts as the primary video sink.
*   Implement the simple Chaos Gating (Frame Difference / SSIM) to decide when to drop frames.

**Phase 2: Dynamic SLAM Bindings**
*   Modify `mono_topological_screencast.cc` to accept dynamic parameter updates via STDIN or a fast IPC socket (ZeroMQ / Redis). 
*   Implement the target-KP PID loop natively inside the ORB extractor wrapper.

**Phase 3: VLM Integration**
*   Connect the VLM baseline script to the Controller. When the SLAM outputs a finalized `place_keyframes/*.png`, the Controller async-queues it to the VLM.

---

## 5. Design Space Exploration (DSE)

To build a truly robust controller, we cannot guess the PID weights or chaos thresholds. We must systematically map the design space.

### Parameters to Explore (The Design Space)
1.  **Reflex Constraints:** `target_keypoints` (500 to 2000), `hash_similarity_threshold` (0.75 to 0.95), `affine_min_inliers` (5 to 30).
2.  **Chaos Metrics:** `motion_variance_threshold` (What level of frame-difference dictates "Chaos"?).
3.  **VLM Polling Rate:** Minimum temporal cooldown between VLM calls (e.g., 1.0s vs 5.0s).

### Optimization Objectives
The DSE will use a Multi-Objective Optimization algorithm (e.g., NSGA-II or Bayesian Optimization via Optuna) to balance three conflicting goals:
1.  **Minimize Latency/Compute:** Maximize FPS. Keep SLAM tracking fast; minimize VLM API calls.
2.  **Minimize Graph Edit Distance (GED):** The final graph must perfectly match the VideoCUA action-log ground truth.
3.  **Maximize Semantic Accuracy:** Ensure no distinct functional states are merged.

### Execution Strategy
1.  Define a hyperparameter sweep configuration using `Optuna`.
2.  Run the `eval_harness.py` iteratively across 10 diverse VideoCUA tasks (spanning dense text, video editors, and flat PDF forms).
3.  Plot the Pareto frontier of Cost vs. Accuracy to determine the optimal starting weights for the dynamic Controller.