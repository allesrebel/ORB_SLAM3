# Task B held-out validation — 2026-05-01

**Task ID:** OnlyOffice_Forms/41768
**Run ID:** 2026-05-01_18-28-09
**Reference (Task A):** OnlyOffice_Forms/41765, Run 2026-05-01_18-26-35

## Quantitative

| Tier | Task A (dev fixture) | Task B (held-out) |
|------|---------------------|-------------------|
| Resolution | 1920×1080 | 1362×722 |
| Frames | 587 | 506 |
| Duration | 19.6 s | 16.9 s |
| Tier 1 (ran) | PASS | PASS |
| Tier 2 (baseline geometric) | FAIL (0 KFs, 0 MPs) | **PASS** (3 KFs, 818 MPs) |
| Tier 3 (topo place graph) | PASS (2 places, 1 edge, depth=0.63) | PASS (2 places, 1 edge, depth=0.74) |
| Topo wall time | 26.2 s | 13.3 s (38 fps) |

## Qualitative

- Both tasks segmented into exactly 2 places connected by a single "new" transition edge — the topological algorithm fired place birth correctly on both.
- Task B's transition depth (0.74) is higher than Task A's (0.63), indicating a more visually distinct change — consistent with the action_log: Task B is "Select the form2 for the title" (a focused state change), Task A is the longer "Add checkboxes and dropdown options" (more incremental).
- Place keyframes for Task A (frame 0 vs frame 85) and Task B (frame 0 vs frame 326) saved to `<run>/topological/place_keyframes/`.
- Surprise: ORB-SLAM3's geometric back-end initialized on Task B (3 KFs, 818 MPs) despite the spec's prediction that screen recordings should not yield non-degenerate maps. Likely due to the lower resolution introducing aliasing that resembles parallax features. This is interesting — geometric init is *occasionally* possible on real screencasts, contrary to my pessimistic prior.
- The yaml's intrinsics (1920×1080) don't match Task B's resolution (1362×722). Despite the mismatch, the topo binary doesn't care about intrinsics (it uses only ORBextractor params and BoW vocab), and the baseline still managed to converge — albeit on incorrect geometry.

## Issues / next steps for v2

1. **Resolution-aware yaml selection.** A future per-task runner should detect the video resolution and pick a matching yaml (or generate one on the fly with rescaled intrinsics). Currently we'd want to defer using baseline tier-2 results until intrinsics are correct.
2. **Generalization of TAU thresholds.** Task A's score distribution was mean=0.37, range 0.28-1.0; thresholds were tuned to that. Task B's distribution may differ; the fact that both produced plausible 2-place segmentations suggests the thresholds generalize reasonably for OnlyOffice Forms. Cross-app validation is the next test (download a different app's ZIP).
3. **Action-log alignment.** Task B has 2 recorded actions in `action_log.json`. The topo binary detected 1 transition edge. Comparing transition timestamps (frame 326 = ~10.9s) against action_log timestamps would let us assess whether the topo segmentation tracks user-meaningful events.
4. **Loop closure not exercised.** Both tasks produced "new" edges only, no "revisit" edges. The OnlyOffice Forms recordings are linear — no back-navigation. To validate the revisit path, we need a task with at least one return-to-prior-state, e.g., a browser session with a "back" button.
