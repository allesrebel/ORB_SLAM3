#!/usr/bin/env python3
"""Selective downloader for the ServiceNow/VideoCUA dataset on HuggingFace.

VideoCUA is distributed as 87 per-application ZIP files under raw_data/.
Each ZIP contains directories named by numeric task ID, each holding:
    <task>/action_log.json
    <task>/video/video.mp4
    <task>/video/video_metadata.json

This tool exposes both the per-app ZIP primitive and per-task task IDs of
the form "<app>/<numeric_task>" (e.g. "OnlyOffice_Forms/41765"). The app
name is the ZIP basename with spaces replaced by underscores so the ID
is shell-safe.

Modes (mutually exclusive):
  --list-apps                     Print available app names (87 entries).
  --list                          Print task IDs already extracted locally.
  --app <name>                    Download + unzip one app to <local-dir>/<app>/.
  --task-id <app>/<task>          Ensure one task is downloaded (pulls + unzips
                                  the parent app's ZIP if needed).
  --whitelist <file>              Ensure every task ID listed (one per line) in
                                  FILE is downloaded.

Optionally reads HF_TOKEN from the environment for authenticated access.
"""
import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

REPO_ID = "ServiceNow/VideoCUA"
REPO_TYPE = "dataset"
DEFAULT_LOCAL_DIR = Path("/opt/rebel/topo_research_artifacts/dataset")
ZIP_CACHE_DIR = Path("/opt/rebel/topo_research_artifacts/.hf_cache/videocua_zips")  # persistent cache for ZIPs


def _sanitize_app(name: str) -> str:
    """Map a raw ZIP basename (e.g. 'OnlyOffice Forms') to a shell-safe dir name."""
    return name.replace(" ", "_")


def _hf_api():
    from huggingface_hub import HfApi
    return HfApi(token=os.environ.get("HF_TOKEN"))


def list_apps() -> list[tuple[str, str]]:
    """Return [(sanitized_name, raw_zip_basename)] sorted by sanitized name."""
    api = _hf_api()
    infos = api.list_repo_tree(repo_id=REPO_ID, repo_type=REPO_TYPE,
                               path_in_repo="raw_data", recursive=False)
    apps = []
    for it in infos:
        # Path looks like 'raw_data/OnlyOffice Forms.zip'
        base = Path(it.path).name
        if not base.endswith(".zip"):
            continue
        raw = base[:-4]
        apps.append((_sanitize_app(raw), raw))
    apps.sort(key=lambda t: t[0])
    return apps


def list_local_task_ids(local_dir: Path) -> list[str]:
    """Return task IDs (in '<app>/<task>' form) that exist on disk."""
    if not local_dir.is_dir():
        return []
    out = []
    for app_dir in sorted(local_dir.iterdir()):
        if not app_dir.is_dir() or app_dir.name.startswith("."):
            continue
        for task_dir in sorted(app_dir.iterdir()):
            if not task_dir.is_dir():
                continue
            if (task_dir / "video" / "video.mp4").is_file():
                out.append(f"{app_dir.name}/{task_dir.name}")
    return out


def download_and_extract_app(app_sanitized: str, local_dir: Path) -> Path:
    """Download <app>.zip from the repo (if not cached) and extract to <local_dir>/<app>/."""
    from huggingface_hub import hf_hub_download

    # Find the raw (un-sanitized) name from the repo listing.
    raw = None
    for s, r in list_apps():
        if s == app_sanitized:
            raw = r
            break
    if raw is None:
        raise ValueError(f"Unknown app: {app_sanitized!r}. "
                         f"Run --list-apps to see valid names.")

    target_dir = local_dir / app_sanitized
    if target_dir.is_dir() and any(target_dir.iterdir()):
        # Already extracted.
        return target_dir

    print(f"Downloading {raw}.zip ...")
    zip_path = hf_hub_download(
        repo_id=REPO_ID, repo_type=REPO_TYPE,
        filename=f"raw_data/{raw}.zip",
        local_dir=str(ZIP_CACHE_DIR),
        token=os.environ.get("HF_TOKEN"),
    )
    print(f"Extracting -> {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(target_dir)
    return target_dir


def ensure_task(task_id: str, local_dir: Path) -> Path:
    """Ensure '<app>/<task>' is on disk; pull + extract its app ZIP if missing.

    Returns the absolute path to the task directory.
    """
    if "/" not in task_id:
        raise ValueError(f"task_id must be '<app>/<task>', got: {task_id!r}")
    app, task = task_id.split("/", 1)
    task_dir = local_dir / app / task
    if (task_dir / "video" / "video.mp4").is_file():
        return task_dir
    download_and_extract_app(app, local_dir)
    if not (task_dir / "video" / "video.mp4").is_file():
        raise RuntimeError(f"Task not found after extracting {app}: {task_dir}")
    return task_dir


def validate_task(task_dir: Path) -> list[str]:
    """Return list of missing required files (empty if OK)."""
    required = ["video/video.mp4", "action_log.json", "video/video_metadata.json"]
    return [r for r in required if not (task_dir / r).is_file()]


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list-apps", action="store_true",
                   help="Print available app names and exit.")
    g.add_argument("--list", action="store_true",
                   help="Print already-extracted task IDs (<app>/<task>) and exit.")
    g.add_argument("--app", type=str, metavar="NAME",
                   help="Download + unzip a single app.")
    g.add_argument("--task-id", type=str, metavar="ID",
                   help="Ensure one '<app>/<task>' is on disk.")
    g.add_argument("--whitelist", type=Path, metavar="FILE",
                   help="Ensure every task ID listed in FILE is on disk.")
    p.add_argument("--local-dir", type=Path, default=DEFAULT_LOCAL_DIR,
                   help=f"Where to put downloads (default: {DEFAULT_LOCAL_DIR}).")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.list_apps:
        for s, _ in list_apps():
            print(s)
        return 0

    if args.list:
        for tid in list_local_task_ids(args.local_dir):
            print(tid)
        return 0

    if args.app:
        out = download_and_extract_app(args.app, args.local_dir)
        n_tasks = sum(1 for _ in out.iterdir() if _.is_dir())
        print(f"OK: {out} ({n_tasks} task dirs extracted)")
        return 0

    if args.task_id:
        out = ensure_task(args.task_id, args.local_dir)
        missing = validate_task(out)
        if missing:
            print(f"FAIL: missing files in {out}: {missing}", file=sys.stderr)
            return 2
        print(f"OK: {out}")
        return 0

    if args.whitelist:
        if not args.whitelist.is_file():
            print(f"FAIL: whitelist file not found: {args.whitelist}",
                  file=sys.stderr)
            return 1
        ids = [line.strip() for line in args.whitelist.read_text().splitlines()
               if line.strip() and not line.startswith("#")]
        bad = []
        for tid in ids:
            try:
                out = ensure_task(tid, args.local_dir)
                missing = validate_task(out)
                if missing:
                    bad.append((tid, missing))
                    continue
                print(f"OK: {out}")
            except Exception as e:
                bad.append((tid, str(e)))
        if bad:
            print(f"FAIL: {len(bad)} task(s) failed: {bad}", file=sys.stderr)
            return 2
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
