#!/usr/bin/env python3
"""Visualize topological place-graph SLAM outputs from /root/orbslam3_runs/VideoCUA/.

Per-task plots (saved into the run's topological/ dir):
  place_timeline.png      Horizontal bar of frame ranges colored by place_id,
                          with transitions marked.
  scores.png              Per-frame DBoW2 score with TAU thresholds and
                          place-transition annotations.
  place_graph.png         Node-edge diagram of the topological graph
                          (force-laid-out via simple circular layout when
                          n_places <= 12, else a chain layout).
  place_keyframes.png     Grid of representative keyframe thumbnails per place.

Cross-task summary plot (saved to <out-dir>/cross_task_summary.png):
  bars per task showing n_places, n_edges, max edge depth, and tier flags.
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np
import cv2

DEFAULT_RUNS_ROOT = Path("/root/orbslam3_runs/VideoCUA")
DEFAULT_OUT_DIR = Path("/root/orbslam3_runs/visualizations")

# match the C++ binary's compiled-in thresholds
TAU_SAME = 0.40
TAU_REVISIT = 0.55


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def latest_run(task_dir: Path) -> Path | None:
    runs = [d for d in task_dir.iterdir() if d.is_dir()]
    return sorted(runs, key=lambda p: p.name)[-1] if runs else None


def discover_runs(runs_root: Path) -> list[tuple[str, Path]]:
    """Return (task_id, run_dir) pairs for the latest run of each task."""
    out = []
    for lvl1 in sorted(runs_root.iterdir()):
        if not lvl1.is_dir():
            continue
        # is lvl1 itself a task dir?
        if any((c / "topological").is_dir() or (c / "baseline").is_dir()
               for c in lvl1.iterdir() if c.is_dir()):
            run = latest_run(lvl1)
            if run is not None:
                out.append((lvl1.name, run))
            continue
        # otherwise recurse one level
        for lvl2 in sorted(lvl1.iterdir()):
            if not lvl2.is_dir():
                continue
            if any((c / "topological").is_dir() or (c / "baseline").is_dir()
                   for c in lvl2.iterdir() if c.is_dir()):
                run = latest_run(lvl2)
                if run is not None:
                    out.append((f"{lvl1.name}/{lvl2.name}", run))
    return out


def load_topo(run_dir: Path) -> dict | None:
    pg = run_dir / "topological" / "place_graph.json"
    if not pg.is_file():
        return None
    return json.loads(pg.read_text())


def load_scores(run_dir: Path) -> tuple[np.ndarray, np.ndarray] | None:
    sp = run_dir / "topological" / "scores.csv"
    if not sp.is_file():
        return None
    frames, scores = [], []
    with sp.open() as f:
        next(f, None)  # header
        for line in f:
            parts = line.strip().split(",")
            if len(parts) != 2:
                continue
            try:
                frames.append(int(parts[0])); scores.append(float(parts[1]))
            except ValueError:
                continue
    return np.array(frames), np.array(scores)


# ---------------------------------------------------------------------------
# per-task plots
# ---------------------------------------------------------------------------
def plot_place_timeline(graph: dict, run_dir: Path, task_id: str) -> None:
    places = graph["places"]
    edges = graph["edges"]
    n_frames = graph["n_frames"]

    fig, ax = plt.subplots(figsize=(11, 2.6))
    cmap = plt.colormaps["tab20"]
    for p in places:
        c0, c1 = p["frame_range"]
        ax.barh(0, c1 - c0 + 1, left=c0, height=0.6,
                color=cmap(p["id"] % 20),
                edgecolor="black", linewidth=0.4)
        ax.text((c0 + c1) / 2, 0, str(p["id"]),
                ha="center", va="center", fontsize=9, color="white",
                weight="bold")

    # mark transitions
    for e in edges:
        x = e["frame"]
        ls = "-" if e["type"] == "new" else "--"
        ax.axvline(x, color="black", lw=1.2, ls=ls, alpha=0.7)
        ax.text(x, 0.45, f'{e["from"]}→{e["to"]}\nd={e["depth"]:.2f}',
                ha="center", va="bottom", fontsize=7,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="grey",
                          alpha=0.85))

    ax.set_xlim(-1, n_frames + 1)
    ax.set_ylim(-0.5, 1.2)
    ax.set_yticks([])
    ax.set_xlabel("frame")
    ax.set_title(f"Place timeline — {task_id}  ({len(places)} places, "
                 f"{len(edges)} transitions, {n_frames} frames)")

    legend = [Line2D([0], [0], color="black", lw=1.2, label="new"),
              Line2D([0], [0], color="black", lw=1.2, ls="--", label="revisit")]
    ax.legend(handles=legend, loc="upper right", fontsize=8)
    plt.tight_layout()
    out = run_dir / "topological" / "place_timeline.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"  wrote {out}")


def plot_scores(graph: dict, scores_data, run_dir: Path, task_id: str) -> None:
    if scores_data is None:
        return
    frames, scores = scores_data
    edges = graph["edges"]

    fig, ax = plt.subplots(figsize=(11, 3.2))
    ax.plot(frames, scores, color="steelblue", lw=0.8, alpha=0.85,
            label="DBoW2 score(frame, current_place_rep)")
    ax.axhline(TAU_SAME, color="orange", lw=1.0, ls="--",
               label=f"TAU_SAME = {TAU_SAME}")
    ax.axhline(TAU_REVISIT, color="red", lw=1.0, ls="--",
               label=f"TAU_REVISIT = {TAU_REVISIT}")

    for e in edges:
        x = e["frame"]
        ls = "-" if e["type"] == "new" else ":"
        ax.axvline(x, color="green" if e["type"] == "new" else "purple",
                   lw=1.0, ls=ls, alpha=0.7)
        ax.annotate(f'{e["from"]}→{e["to"]}',
                    xy=(x, 0.95), xycoords=("data", "axes fraction"),
                    ha="center", fontsize=7, color="darkgreen",
                    rotation=0)

    ax.set_xlabel("frame")
    ax.set_ylabel("DBoW2 score")
    ax.set_xlim(0, scores.size)
    ax.set_ylim(0, max(1.05, float(scores.max()) * 1.05))
    ax.set_title(f"Score over time — {task_id}")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.25)
    plt.tight_layout()
    out = run_dir / "topological" / "scores.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"  wrote {out}")


def plot_graph(graph: dict, run_dir: Path, task_id: str) -> None:
    places = graph["places"]
    edges = graph["edges"]
    n = len(places)

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    if n <= 1:
        ax.text(0.5, 0.5, f"only {n} place — no graph",
                ha="center", va="center", transform=ax.transAxes)
    else:
        # circular layout for compact graphs, chain layout for long ones
        if n <= 12:
            angles = np.linspace(0, 2 * np.pi, n, endpoint=False) - np.pi / 2
            xs = np.cos(angles); ys = np.sin(angles)
        else:
            xs = np.linspace(-1, 1, n); ys = 0.2 * np.sin(np.linspace(0, 4 * np.pi, n))

        cmap = plt.colormaps["tab20"]
        for i, p in enumerate(places):
            ax.scatter([xs[i]], [ys[i]], s=900, c=[cmap(p["id"] % 20)],
                       edgecolors="black", zorder=3)
            ax.text(xs[i], ys[i], str(p["id"]), ha="center", va="center",
                    fontsize=10, weight="bold", color="white", zorder=4)

        for e in edges:
            i, j = e["from"], e["to"]
            color = "darkgreen" if e["type"] == "new" else "purple"
            ls = "-" if e["type"] == "new" else "--"
            ax.annotate(
                "",
                xy=(xs[j], ys[j]), xytext=(xs[i], ys[i]),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.6,
                                ls=ls, shrinkA=15, shrinkB=15,
                                connectionstyle="arc3,rad=0.18"),
            )
            mx, my = (xs[i] + xs[j]) / 2, (ys[i] + ys[j]) / 2
            ax.text(mx, my + 0.1, f'd={e["depth"]:.2f}',
                    ha="center", fontsize=7, color=color)

        ax.set_xlim(-1.6, 1.6); ax.set_ylim(-1.4, 1.4)
        ax.set_aspect("equal")

    ax.set_axis_off()
    ax.set_title(f"Place graph — {task_id}\n"
                 f"{n} place(s), {len(edges)} edge(s)")
    plt.tight_layout()
    out = run_dir / "topological" / "place_graph.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"  wrote {out}")


def plot_keyframes(graph: dict, run_dir: Path, task_id: str) -> None:
    places = graph["places"]
    n = len(places)
    if n == 0:
        return
    cols = min(n, 4)
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.4, rows * 2.4),
                             squeeze=False)
    for ax in axes.flat:
        ax.set_axis_off()
    for i, p in enumerate(places):
        r, c = i // cols, i % cols
        img_path = run_dir / "topological" / p["keyframe_image"]
        if img_path.is_file():
            img = cv2.imread(str(img_path))
            if img is not None:
                axes[r, c].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        axes[r, c].set_title(f"place {p['id']}\nframes "
                             f"{p['frame_range'][0]}-{p['frame_range'][1]}",
                             fontsize=8)
    fig.suptitle(f"Place keyframes — {task_id}", fontsize=11)
    plt.tight_layout()
    out = run_dir / "topological" / "place_keyframes.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(f"  wrote {out}")


# ---------------------------------------------------------------------------
# cross-task summary
# ---------------------------------------------------------------------------
def plot_cross_task_summary(rows: list[dict], out_dir: Path) -> None:
    if not rows:
        print("No tasks to summarize")
        return
    rows = sorted(rows, key=lambda r: r["task_id"])
    labels = [r["task_id"] for r in rows]
    n_places = [r["n_places"] for r in rows]
    n_edges = [r["n_edges"] for r in rows]
    max_depths = [r["max_depth"] for r in rows]
    tier1 = [r["tier1"] for r in rows]
    tier2 = [r["tier2"] for r in rows]
    tier3 = [r["tier3"] for r in rows]

    y = np.arange(len(rows))
    fig, axes = plt.subplots(1, 3, figsize=(15, max(4, 0.45 * len(rows))),
                             sharey=True,
                             gridspec_kw={"width_ratios": [3, 3, 4]})

    # 1. n_places + n_edges side-by-side
    ax = axes[0]
    bw = 0.4
    ax.barh(y - bw/2, n_places, bw, color="tab:blue", label="n_places")
    ax.barh(y + bw/2, n_edges,  bw, color="tab:orange", label="n_edges")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_title("Place count vs edge count")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="x", alpha=0.3)

    # 2. max edge depth
    ax = axes[1]
    bars = ax.barh(y, max_depths, color="tab:green")
    for i, d in enumerate(max_depths):
        ax.text(d + 0.01, i, f"{d:.2f}" if d > 0 else "—",
                va="center", fontsize=7)
    ax.set_xlim(0, 1.05)
    ax.set_title("Max edge depth")
    ax.grid(axis="x", alpha=0.3)

    # 3. tier flags
    ax = axes[2]
    tier_array = np.array([tier1, tier2, tier3]).T  # shape (n, 3)
    ax.imshow(tier_array, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["tier 1\nran", "tier 2\nbaseline", "tier 3\ntopo"],
                       fontsize=8)
    for i in range(len(rows)):
        for j in range(3):
            ax.text(j, i, "✓" if tier_array[i, j] else "✗",
                    ha="center", va="center",
                    color="white", weight="bold")
    ax.set_title("Tier classification")

    fig.suptitle(f"Cross-task summary  ({len(rows)} tasks)",
                 fontsize=12, weight="bold")
    plt.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "cross_task_summary.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"\nwrote {out}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def collect_summary_row(task_id: str, run_dir: Path) -> dict | None:
    graph = load_topo(run_dir)
    if not graph:
        return None
    edges = graph["edges"]
    max_d = max((e["depth"] for e in edges), default=0.0)
    base = run_dir / "baseline"
    topo = run_dir / "topological"
    tier1 = (base / "run.log").is_file() and (topo / "run.log").is_file()
    # parse SessionInfo for tier 2
    session = base / "SessionInfo.txt"
    kfs = mps = 0
    if session.is_file():
        import re
        text = session.read_text(errors="replace")
        m = re.search(r"Number of KFs[^0-9]*(\d+)", text)
        if m: kfs = int(m.group(1))
        m = re.search(r"Number of MPs[^0-9]*(\d+)", text)
        if m: mps = int(m.group(1))
    traj = base / "KeyFrameTrajectory.txt"
    traj_lines = sum(1 for line in traj.open() if line.strip()) if traj.is_file() else 0
    tier2 = kfs > 0 and mps > 0 and traj_lines > 0
    tier3 = len(graph["places"]) >= 2 and len(edges) >= 1
    return {"task_id": task_id, "n_places": len(graph["places"]),
            "n_edges": len(edges), "max_depth": max_d,
            "tier1": int(tier1), "tier2": int(tier2), "tier3": int(tier3)}


def visualize_one(task_id: str, run_dir: Path) -> dict | None:
    graph = load_topo(run_dir)
    if graph is None:
        print(f"[skip] no topological output for {task_id}")
        return None
    print(f"[viz] {task_id}  -> {run_dir}")
    plot_place_timeline(graph, run_dir, task_id)
    plot_scores(graph, load_scores(run_dir), run_dir, task_id)
    plot_graph(graph, run_dir, task_id)
    plot_keyframes(graph, run_dir, task_id)
    return collect_summary_row(task_id, run_dir)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    p.add_argument("--out-dir",   type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--task",      type=str, default=None,
                   help="Visualize one specific task ID instead of all.")
    args = p.parse_args(argv)

    pairs = discover_runs(args.runs_root)
    if args.task:
        pairs = [(t, r) for t, r in pairs if t == args.task]
        if not pairs:
            print(f"FAIL: task {args.task!r} not found", file=sys.stderr)
            return 1

    rows = []
    for tid, run in pairs:
        row = visualize_one(tid, run)
        if row:
            rows.append(row)

    if not args.task:
        plot_cross_task_summary(rows, args.out_dir)

    print(f"\nDone — visualized {len(rows)} task(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
