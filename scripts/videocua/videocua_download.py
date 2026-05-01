#!/usr/bin/env python3
"""Selective downloader for the ServiceNow/VideoCUA dataset on HuggingFace.

Three modes (mutually exclusive):
  --list                          Print available task IDs (one per line).
  --task-id <id>                  Download a single task to <local-dir>/<id>/.
  --whitelist <file>              Download every task ID listed in <file>.

Optionally reads HF_TOKEN from the environment for authenticated access.
"""
import argparse
import os
import sys
from pathlib import Path

REPO_ID = "ServiceNow/VideoCUA"
REPO_TYPE = "dataset"
DEFAULT_LOCAL_DIR = Path("/root/VideoCUA")


def _hf_api():
    from huggingface_hub import HfApi
    return HfApi(token=os.environ.get("HF_TOKEN"))


def list_task_ids() -> list[str]:
    """Return sorted unique top-level directory names in the repo."""
    api = _hf_api()
    files = api.list_repo_files(repo_id=REPO_ID, repo_type=REPO_TYPE)
    task_ids = set()
    for f in files:
        head = f.split("/", 1)[0]
        # Skip top-level metadata files (README.md, .gitattributes, etc.)
        if "/" in f and head and not head.startswith("."):
            task_ids.add(head)
    return sorted(task_ids)


def download_task(task_id: str, local_dir: Path) -> Path:
    """Pull all files under <task_id>/ into <local_dir>/<task_id>/."""
    from huggingface_hub import snapshot_download
    local_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        allow_patterns=[f"{task_id}/*", f"{task_id}/**/*"],
        local_dir=str(local_dir),
        token=os.environ.get("HF_TOKEN"),
    )
    out = local_dir / task_id
    if not out.is_dir():
        raise RuntimeError(f"Download finished but {out} does not exist")
    return out


def validate_task(task_dir: Path) -> list[str]:
    """Return list of missing required files (empty if OK)."""
    required = ["video/video.mp4", "action_log.json", "video/video_metadata.json"]
    missing = [r for r in required if not (task_dir / r).is_file()]
    return missing


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true",
                   help="Print available task IDs and exit.")
    g.add_argument("--task-id", type=str, metavar="ID",
                   help="Download a single task by ID.")
    g.add_argument("--whitelist", type=Path, metavar="FILE",
                   help="Download every task ID listed (one per line) in FILE.")
    p.add_argument("--local-dir", type=Path, default=DEFAULT_LOCAL_DIR,
                   help=f"Where to put downloads (default: {DEFAULT_LOCAL_DIR}).")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.list:
        for tid in list_task_ids():
            print(tid)
        return 0

    if args.task_id:
        out = download_task(args.task_id, args.local_dir)
        missing = validate_task(out)
        if missing:
            print(f"FAIL: missing files in {out}: {missing}", file=sys.stderr)
            return 2
        print(f"OK: {out}")
        return 0

    if args.whitelist:
        if not args.whitelist.is_file():
            print(f"FAIL: whitelist file not found: {args.whitelist}", file=sys.stderr)
            return 1
        ids = [line.strip() for line in args.whitelist.read_text().splitlines()
               if line.strip() and not line.startswith("#")]
        bad = []
        for tid in ids:
            try:
                out = download_task(tid, args.local_dir)
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
