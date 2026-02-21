#!/usr/bin/env python3
"""
reviewer_run.py — one-command reproducibility runner

What it does:
- Runs Go tests (unit/integration/security) and benchmarks
- Captures environment metadata + git commit
- Writes artifacts to docs/evidence/out/<timestamp>/
- Generates INDEX.md + SHA256SUMS
- Optionally runs IBM Runtime smoke test if configured (skips otherwise)

Usage:
  python reviewer_run.py
  python reviewer_run.py --no-bench
  python reviewer_run.py --ibm   (attempt IBM smoke test if creds are set)
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT_BASE = ROOT / "docs" / "evidence" / "out"

GO_PACKAGES = ["./..."]
GO_TEST_TIMEOUT = "10m"


@dataclasses.dataclass
class CmdResult:
    cmd: List[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int


def run_cmd(cmd: List[str], cwd: Path = ROOT, env: Optional[Dict[str, str]] = None) -> CmdResult:
    start = dt.datetime.now(dt.timezone.utc)
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        env={**os.environ, **(env or {})},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    end = dt.datetime.now(dt.timezone.utc)
    dur_ms = int((end - start).total_seconds() * 1000)
    return CmdResult(cmd=cmd, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr, duration_ms=dur_ms)


def try_get_git_commit() -> str:
    if not (ROOT / ".git").exists():
        return "unknown"
    r = run_cmd(["git", "rev-parse", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def try_get_git_status_short() -> str:
    if not (ROOT / ".git").exists():
        return ""
    r = run_cmd(["git", "status", "--porcelain"])
    return r.stdout.strip()


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_text(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")


def write_json(p: Path, obj: Any) -> None:
    p.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_ibm_config_present() -> bool:
    # Minimal check — adapt to your preferred auth mechanism:
    # - IBM_QUANTUM_TOKEN, or qiskit saved account, or local config file
    return bool(os.environ.get("IBM_QUANTUM_TOKEN") or os.environ.get("QISKIT_IBM_TOKEN"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT_BASE), help="Base output directory (default: docs/evidence/out)")
    ap.add_argument("--no-bench", action="store_true", help="Skip Go benchmarks")
    ap.add_argument("--ibm", action="store_true", help="Attempt IBM Runtime smoke test if configured")
    args = ap.parse_args()

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_base = Path(args.out)
    out_dir = out_base / ts
    ensure_dir(out_dir)

    commit = try_get_git_commit()
    dirty = try_get_git_status_short()
    meta = {
        "artifact_type": "reviewer_run_bundle",
        "created_utc": ts,
        "repo_root": str(ROOT),
        "git_commit": commit,
        "git_dirty": bool(dirty),
        "git_status_porcelain": dirty,
        "platform": {
            "python": sys.version.replace("\n", " "),
            "os": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
    }
    write_json(out_dir / "run_metadata.json", meta)

    results: Dict[str, Any] = {"meta": meta, "steps": []}

    # 1) Go tests (all)
    test_cmd = ["go", "test", "-timeout", GO_TEST_TIMEOUT, "-v"] + GO_PACKAGES
    r_test = run_cmd(test_cmd)
    write_text(out_dir / "go_test_stdout.txt", r_test.stdout)
    write_text(out_dir / "go_test_stderr.txt", r_test.stderr)
    results["steps"].append(dataclasses.asdict(r_test))

    # 2) Go benchmarks
    if not args.no_bench:
        bench_cmd = ["go", "test", "-run", "^$", "-bench", ".", "-benchmem"] + GO_PACKAGES
        r_bench = run_cmd(bench_cmd)
        write_text(out_dir / "go_bench_stdout.txt", r_bench.stdout)
        write_text(out_dir / "go_bench_stderr.txt", r_bench.stderr)
        results["steps"].append(dataclasses.asdict(r_bench))

    # 3) Optional IBM smoke test
    ibm_r = None
    if args.ibm:
        if is_ibm_config_present():
            # If you keep a dedicated smoke test file, call it here.
            # Example assumes you add scripts/ibm_smoke_test.py in repo.
            smoke = ROOT / "scripts" / "ibm_smoke_test.py"
            if smoke.exists():
                ibm_r = run_cmd([sys.executable, str(smoke)])
                write_text(out_dir / "ibm_smoke_stdout.txt", ibm_r.stdout)
                write_text(out_dir / "ibm_smoke_stderr.txt", ibm_r.stderr)
                results["steps"].append(dataclasses.asdict(ibm_r))
            else:
                note = "IBM smoke test requested, but scripts/ibm_smoke_test.py not found. Skipped."
                write_text(out_dir / "ibm_smoke_NOTE.txt", note)
                results["steps"].append({"cmd": ["<missing>"], "returncode": 0, "stdout": note, "stderr": "", "duration_ms": 0})
        else:
            note = "IBM smoke test requested, but no IBM credentials detected in environment. Skipped."
            write_text(out_dir / "ibm_smoke_NOTE.txt", note)
            results["steps"].append({"cmd": ["<skipped>"], "returncode": 0, "stdout": note, "stderr": "", "duration_ms": 0})

    # 4) Summarize into INDEX.md
    def ok(rc: int) -> str:
        return "✅" if rc == 0 else "❌"

    lines = []
    lines.append(f"# Reviewer Run Bundle — {ts}")
    lines.append("")
    lines.append(f"- Git commit: `{commit}`")
    lines.append(f"- Dirty working tree: `{bool(dirty)}`")
    lines.append("")
    lines.append("## Outputs")
    lines.append("")
    lines.append(f"- `run_metadata.json` — environment + commit")
    lines.append(f"- `go_test_stdout.txt` / `go_test_stderr.txt`")
    if not args.no_bench:
        lines.append(f"- `go_bench_stdout.txt` / `go_bench_stderr.txt`")
    if args.ibm:
        lines.append(f"- `ibm_smoke_*` — IBM smoke test logs (or NOTE if skipped)")
    lines.append("")
    lines.append("## Step Results")
    lines.append("")
    for step in results["steps"]:
        if isinstance(step, dict) and "cmd" in step and "returncode" in step:
            cmd_str = " ".join(step["cmd"]) if isinstance(step["cmd"], list) else str(step["cmd"])
            lines.append(f"- {ok(step['returncode'])} `{cmd_str}`  (rc={step['returncode']}, {step.get('duration_ms', 0)} ms)")
    lines.append("")
    lines.append("## Integrity")
    lines.append("")
    lines.append("- `SHA256SUMS` — checksums for all files in this bundle")
    lines.append("")
    write_text(out_dir / "INDEX.md", "\n".join(lines))

    # 5) Write full JSON
    write_json(out_dir / "results.json", results)

    # 6) SHA256SUMS
    sums = []
    for p in sorted(out_dir.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            sums.append(f"{sha256_file(p)}  {p.name}")
    write_text(out_dir / "SHA256SUMS", "\n".join(sums) + "\n")

    # Exit code: fail if any required step fails
    required_fail = (r_test.returncode != 0) or ((not args.no_bench) and any(
        (isinstance(s, dict) and s.get("cmd", [""])[0] == "go" and " -bench " in " ".join(s.get("cmd", [])) and s.get("returncode") != 0)
        for s in results["steps"]
    ))
    return 1 if required_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())