"""Verify that classification logic against synthetic on-disk run dirs is correct."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "verify_and_whitelist.py"


def _make_task_run(root: Path, task_id: str, *,
                   baseline_log: bool, baseline_kfs: int, baseline_mps: int,
                   topo_log: bool, n_places: int, n_edges: int) -> None:
    run_dir = root / task_id / "2026-05-01_00-00-00"
    base = run_dir / "baseline"; base.mkdir(parents=True, exist_ok=True)
    topo = run_dir / "topological"; topo.mkdir(parents=True, exist_ok=True)
    if baseline_log:
        (base / "run.log").write_text("ok\n")
    (base / "KeyFrameTrajectory.txt").write_text(
        ("\n".join(["1 0 0 0 0 0 0 1"] * baseline_kfs) + "\n") if baseline_kfs else "")
    (base / "SessionInfo.txt").write_text(
        f"Number of KFs: {baseline_kfs}\nNumber of MPs: {baseline_mps}\n")
    if topo_log:
        (topo / "run.log").write_text("ok\n")
    (topo / "place_graph.json").write_text(json.dumps({
        "fps": 30, "n_frames": 100,
        "places": [{"id": i} for i in range(n_places)],
        "edges":  [{"from": 0, "to": 1, "depth": 0.3, "type": "new"}
                   for _ in range(n_edges)],
    }))


def test_classifies_three_tiers(tmp_path):
    _make_task_run(tmp_path, "task_pass",
                   baseline_log=True, baseline_kfs=10, baseline_mps=400,
                   topo_log=True, n_places=4, n_edges=3)
    _make_task_run(tmp_path, "task_topo_only",
                   baseline_log=True, baseline_kfs=0, baseline_mps=0,
                   topo_log=True, n_places=2, n_edges=1)
    _make_task_run(tmp_path, "task_ran_only",
                   baseline_log=True, baseline_kfs=0, baseline_mps=0,
                   topo_log=True, n_places=1, n_edges=0)
    _make_task_run(tmp_path, "task_none",
                   baseline_log=False, baseline_kfs=0, baseline_mps=0,
                   topo_log=False, n_places=0, n_edges=0)

    out = tmp_path / "whitelists"
    r = subprocess.run([sys.executable, str(SCRIPT),
                        "--runs-root", str(tmp_path),
                        "--out-dir", str(out)],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr

    ran = (out / "whitelist_ran.txt").read_text().split()
    base = (out / "whitelist_baseline.txt").read_text().split()
    topo = (out / "whitelist_topo.txt").read_text().split()

    assert sorted(ran)  == ["task_pass", "task_ran_only", "task_topo_only"]
    assert sorted(base) == ["task_pass"]
    assert sorted(topo) == ["task_pass", "task_topo_only"]

    summary = (out / "summary.csv").read_text().splitlines()
    assert summary[0].startswith("task_id,tier1_ran,tier2_baseline,tier3_topo,n_places,n_edges")
    assert any(line.startswith("task_pass,") for line in summary[1:])
