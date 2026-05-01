#!/usr/bin/env python3
"""Walk /root/orbslam3_runs/VideoCUA/, classify each task into tiers,
write whitelist files and a summary CSV.

Tier 1 (ran)      — both baseline/run.log and topological/run.log exist.
Tier 2 (baseline) — KeyFrameTrajectory.txt non-empty AND SessionInfo
                     reports KFs > 0 AND MPs > 0.
Tier 3 (topo)     — place_graph.json parses AND len(places) >= 2 AND
                     len(edges) >= 1.

Task IDs may include a slash (form '<app>/<task>') because the runs root
mirrors the VideoCUA/<app>/<task>/<run_id> layout. We walk two directory
levels to recognize this case.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

DEFAULT_RUNS_ROOT = Path("/root/orbslam3_runs/VideoCUA")
DEFAULT_OUT_DIR   = Path("/root/orbslam3_runs/whitelists")


def latest_run(task_dir: Path) -> Path | None:
    runs = [d for d in task_dir.iterdir() if d.is_dir()]
    if not runs:
        return None
    return sorted(runs, key=lambda p: p.name)[-1]


def parse_session_info(p: Path) -> tuple[int, int]:
    if not p.is_file():
        return (0, 0)
    text = p.read_text(errors="replace")
    kfs = mps = 0
    m = re.search(r"Number of KFs[^0-9]*(\d+)", text)
    if m: kfs = int(m.group(1))
    m = re.search(r"Number of MPs[^0-9]*(\d+)", text)
    if m: mps = int(m.group(1))
    return (kfs, mps)


def classify(run_dir: Path) -> dict:
    base = run_dir / "baseline"
    topo = run_dir / "topological"
    out = {
        "tier1_ran":      False,
        "tier2_baseline": False,
        "tier3_topo":     False,
        "kfs": 0, "mps": 0,
        "traj_lines": 0,
        "n_places": 0, "n_edges": 0,
    }

    base_log_ok = (base / "run.log").is_file()
    topo_log_ok = (topo / "run.log").is_file()
    out["tier1_ran"] = base_log_ok and topo_log_ok

    traj = base / "KeyFrameTrajectory.txt"
    if traj.is_file():
        out["traj_lines"] = sum(1 for line in traj.open() if line.strip())
    out["kfs"], out["mps"] = parse_session_info(base / "SessionInfo.txt")
    out["tier2_baseline"] = (out["kfs"] > 0 and out["mps"] > 0
                             and out["traj_lines"] > 0)

    pg = topo / "place_graph.json"
    if pg.is_file():
        try:
            data = json.loads(pg.read_text())
            out["n_places"] = len(data.get("places", []))
            out["n_edges"]  = len(data.get("edges",  []))
            out["tier3_topo"] = (out["n_places"] >= 2 and out["n_edges"] >= 1)
        except Exception:
            pass

    return out


def discover_task_dirs(runs_root: Path) -> list[tuple[str, Path]]:
    """Yield (task_id, task_dir) pairs.

    A task_dir is a directory whose immediate children are run_id directories
    (i.e., we found at least one child that itself contains baseline/ or
    topological/ subdirs). We walk up to 2 levels deep to support the
    '<app>/<task>' layout used by VideoCUA.
    """
    found = []
    for lvl1 in sorted(runs_root.iterdir()):
        if not lvl1.is_dir(): continue
        # Is lvl1 itself a task dir? (children look like run_id timestamps)
        if any((c / "baseline").is_dir() or (c / "topological").is_dir()
               for c in lvl1.iterdir() if c.is_dir()):
            found.append((lvl1.name, lvl1))
            continue
        # Otherwise recurse one level (lvl1 is an "app" dir).
        for lvl2 in sorted(lvl1.iterdir()):
            if not lvl2.is_dir(): continue
            if any((c / "baseline").is_dir() or (c / "topological").is_dir()
                   for c in lvl2.iterdir() if c.is_dir()):
                found.append((f"{lvl1.name}/{lvl2.name}", lvl2))
    return found


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    p.add_argument("--out-dir",   type=Path, default=DEFAULT_OUT_DIR)
    args = p.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    if not args.runs_root.is_dir():
        print(f"FAIL: runs root not found: {args.runs_root}", file=sys.stderr)
        return 1

    rows = []
    for task_id, task_dir in discover_task_dirs(args.runs_root):
        run = latest_run(task_dir)
        if run is None: continue
        cls = classify(run)
        rows.append({"task_id": task_id, **cls})

    ran      = [r["task_id"] for r in rows if r["tier1_ran"]]
    baseline = [r["task_id"] for r in rows if r["tier2_baseline"]]
    topo     = [r["task_id"] for r in rows if r["tier3_topo"]]

    (args.out_dir / "whitelist_ran.txt").write_text(
        "\n".join(ran) + ("\n" if ran else ""))
    (args.out_dir / "whitelist_baseline.txt").write_text(
        "\n".join(baseline) + ("\n" if baseline else ""))
    (args.out_dir / "whitelist_topo.txt").write_text(
        "\n".join(topo) + ("\n" if topo else ""))

    with (args.out_dir / "summary.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "tier1_ran", "tier2_baseline", "tier3_topo",
                    "n_places", "n_edges", "kfs", "mps", "traj_lines"])
        for r in rows:
            w.writerow([r["task_id"], int(r["tier1_ran"]),
                        int(r["tier2_baseline"]), int(r["tier3_topo"]),
                        r["n_places"], r["n_edges"],
                        r["kfs"], r["mps"], r["traj_lines"]])

    print(f"Tasks evaluated: {len(rows)}")
    print(f"  tier1_ran:      {len(ran)}")
    print(f"  tier2_baseline: {len(baseline)}")
    print(f"  tier3_topo:     {len(topo)}")
    print(f"Whitelists: {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
