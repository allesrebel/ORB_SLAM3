# Cross-app trial — 2026-05-01

12 tasks across 6 applications evaluated through the topological place-graph SLAM pipeline.

## Apps and tasks

| App | Tasks | Sizes | Resolutions |
|---|---|---|---|
| OnlyOffice_Forms | 41765, 41768 | 1.8 MB, 8.6 MB | 1920×1080, 1362×722 |
| GrassGIS | 46644, 46646 | varied | varied |
| Conky | 106644, 106670 | varied | varied |
| PDFedit | 47588, 47602 | varied | varied |
| Natron | 45212, 45215 | varied | varied |
| OpenBoard | 51395, 51410 | varied | varied |

## Tier results

| Tier | Pass rate | What it means |
|---|---|---|
| Tier 1 — pipeline ran cleanly | 12/12 | All binaries exited 0 with output logs present |
| Tier 2 — geometric SLAM produced map | 1/12 | Only `OnlyOffice_Forms/41768` initialized a non-degenerate geometric map (3 KFs / 818 MPs) |
| Tier 3 — topo place graph ≥2 places + ≥1 edge | 11/12 | Only `Natron/45215` (4-second video) failed |

## Topological output statistics

| task_id | n_places | n_edges | max_depth | notes |
|---|---|---|---|---|
| Conky/106644 | 5 | 4 | 0.74 | linear chain |
| Conky/106670 | 3 | 2 | 0.77 | linear chain |
| GrassGIS/46644 | 6 | 5 | 0.79 | 48s video, long Place 2 stretch (frames 280-900) |
| GrassGIS/46646 | 3 | 2 | 0.81 | linear chain |
| Natron/45212 | 6 | 5 | **0.91** | linear chain, very distinct transitions |
| Natron/45215 | 1 | 0 | — | 4s video, no transition detected |
| OnlyOffice_Forms/41765 | 2 | 1 | 0.63 | dev fixture |
| OnlyOffice_Forms/41768 | 2 | 1 | 0.74 | held-out, baseline also passed |
| OpenBoard/51395 | 5 | **5** | 0.81 | **n_edges == n_places → loop closure!** |
| OpenBoard/51410 | 7 | 6 | **0.92** | 7 transitions in 133 frames — fast UI sweep |
| PDFedit/47588 | 5 | 4 | 0.81 | linear chain |
| PDFedit/47602 | 2 | 1 | 0.81 | linear chain |

## Highlights

1. **Loop closure detected on OpenBoard/51395** — Place 4 → Place 3 with depth=0.25 (very low — visually similar). The keyframes confirm the semantic interpretation: Place 3 is the clean whiteboard, Place 4 has a settings dialog overlaid; the user closes the dialog at frame ~1000 and returns to Place 3. This is the first end-to-end demonstration of the revisit branch of the algorithm working on real VideoCUA data.

2. **Threshold robustness** — the same `TAU_SAME=0.40, TAU_REVISIT=0.55` thresholds tuned on OnlyOffice Forms produced sensible segmentations across all 6 apps. Place counts scaled with video length and content dynamism (4s/no transition vs 48s/6 places vs 4.4s/7 places — all reasonable for the underlying content).

3. **Geometric SLAM nearly always fails** — confirms the spec's prediction. Only one of 12 tasks initialized a map. The topological abstraction is the productive path.

4. **High max edge depths (0.63 - 0.92)** — most "new" transitions cross substantial visual gaps, indicating that the algorithm is not over-segmenting. The ONE low-depth edge (OpenBoard/51395 4→3 at 0.25) is exactly the loop closure we want to detect.

## Files

- Per-task visualizations: `<run_dir>/topological/{place_timeline,scores,place_graph,place_keyframes}.png`
- Cross-task summary: `/root/orbslam3_runs/visualizations/cross_task_summary.png`
