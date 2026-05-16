# Reproducibility Guide: Hybrid SLAM-VLM Continuous UI Understanding

Thank you for reviewing our work. To ensure total scientific transparency and rigorous reproducibility, we have containerized our entire experimental evaluation into a single, standalone bash script.

## 1. Quick Start
You can instantly reproduce the graphs, tables, and metrics presented in our paper by executing the following command on an Ubuntu/Debian system:

```bash
git clone git@github.com:allesrebel/topo-slam-data.git
cd topo-slam-data
./reproduce.sh
```

## 2. What `reproduce.sh` Does
This script is designed to run without interfering with your global environment. It performs the following steps sequentially:
1. **Isolated Environment:** Creates a local Python virtual environment (`/tmp/reproduce_venv`) and installs the exact versions of `torch`, `transformers`, `scikit-image`, `pandas`, and `optuna`.
2. **Pinned Commit Checkout:** Clones the main `ORB_SLAM3` repository and performs a hard reset to the exact Git commit used for this research publication (`165cd137f62316c77541fe28d18cb06a5ede0551`). This ensures that future commits do not break reproducibility.
3. **C++ Compilation:** Compiles the `mono_topological_screencast` binary from scratch.
4. **Full 50-Task Evaluation:** Downloads the 50 designated tasks from the ServiceNow/VideoCUA dataset, parses the ground truth (filtering out non-state-altering "dead clicks"), and executes the sequence alignment evaluation against all 4 baselines (SSIM, CLIP, BLIP, and our Enhanced Topo-SLAM).
5. **Metric Verification:** Automatically runs a `diff` comparing the newly generated `final_results.csv` against the gold-standard data preserved in this repository's `experiment_data` folder.

## 3. Understanding the Metrics
As noted in the paper, we overhauled our evaluation metrics to ensure topological rigor:
* **tIoU (Temporal Intersection over Union):** Rather than blindly comparing the absolute number of states, our harness represents UI states as temporal intervals `[start_frame, end_frame]` and aligns them using Hungarian Bipartite Matching.
* **True Graph Edit Distance (GED):** State substitutions are penalized by $1 - \text{tIoU}$. The metric fully accounts for False Splits (over-segmentation) and Misses (under-segmentation).
* **Latency Parsing:** The harness extracts the true C++ wall-clock execution time directly from the `mono_topological_screencast` logs, rather than relying on injected constants.

## 4. Design Space Exploration (DSE)
The Optuna sweep generated the Pareto front figure (`pareto_front_real.png`) by running a true Hardware-in-the-Loop simulation. It spawns the C++ binary as a subprocess and dynamically passes parameters (`--target_kp`, `--hash_th`, `--affine_min`) to empirically measure the trade-off between GED and tracking latency on the edge.

If you encounter any issues reproducing this work, please open an issue in the repository!