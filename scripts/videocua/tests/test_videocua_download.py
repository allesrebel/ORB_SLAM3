"""Smoke tests for videocua_download — they exercise CLI parsing only.
Network-bound paths are tested manually in Task 1.2."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "videocua_download.py"

def test_help_prints_usage():
    r = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                       capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    assert "--list-apps" in r.stdout
    assert "--list" in r.stdout
    assert "--app" in r.stdout
    assert "--task-id" in r.stdout
    assert "--whitelist" in r.stdout

def test_no_args_errors():
    r = subprocess.run([sys.executable, str(SCRIPT)],
                       capture_output=True, text=True, timeout=10)
    assert r.returncode != 0

def test_task_id_must_have_slash(tmp_path):
    """ensure_task() should reject IDs without an app/task split."""
    r = subprocess.run([sys.executable, str(SCRIPT),
                        "--task-id", "missing-slash",
                        "--local-dir", str(tmp_path)],
                       capture_output=True, text=True, timeout=10)
    assert r.returncode != 0
    assert "task_id" in (r.stderr + r.stdout).lower() or "<app>" in (r.stderr + r.stdout).lower() or "got:" in (r.stderr + r.stdout).lower()
