#!/usr/bin/env python3
"""
make_evidence_manifest.py (v2)

Generates:
- docs/evidence/manifest.json
- docs/evidence/SHA256SUMS
- docs/evidence/INDEX.md (optional)
- docs/evidence/WARNINGS.md (optional; enabled by default)

It extracts backend/shots/timestamp/job_ids from common JSON evidence patterns,
including nested lists of runs.

Usage:
  python make_evidence_manifest.py
  python make_evidence_manifest.py --evidence docs/evidence
  python make_evidence_manifest.py --write-index
  python make_evidence_manifest.py --no-warnings
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Heuristics: IBM job ids often look like d0... (but keep flexible)
JOB_ID_TOKEN_RE = re.compile(r"\b[a-z0-9]{10,40}\b", re.IGNORECASE)
LIKELY_JOB_PREFIX = ("d0", "c0")  # extend if needed


# ---------------------------
# Utils
# ---------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def try_git_commit(repo_root: Path) -> str:
    if not (repo_root / ".git").exists():
        return "unknown"
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


def ensure_text(s: Any) -> str:
    if isinstance(s, str):
        return s
    return str(s)


def walk_all_values(obj: Any):
    """Yield all leaf values from nested json-like structures."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from walk_all_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_all_values(v)
    else:
        yield obj


def find_first_str(obj: Any, keys: List[str]) -> Optional[str]:
    if not isinstance(obj, dict):
        return None
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def deep_get(obj: Any, path: List[str]) -> Optional[Any]:
    cur = obj
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


# ---------------------------
# Extraction
# ---------------------------

def extract_job_ids_from_text(text: str) -> List[str]:
    cands = JOB_ID_TOKEN_RE.findall(text.lower())
    ids = [c for c in cands if c.startswith(LIKELY_JOB_PREFIX) and len(c) >= 12]
    seen: Set[str] = set()
    out: List[str] = []
    for x in ids:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def extract_job_ids(obj: Any) -> List[str]:
    ids: List[str] = []

    # 1) common direct keys
    if isinstance(obj, dict):
        for k in ("job_id", "jobId", "runtime_job_id"):
            v = obj.get(k)
            if isinstance(v, str):
                ids.append(v)
        for k in ("job_ids", "jobIds", "jobs", "ibm_job_ids"):
            v = obj.get(k)
            if isinstance(v, list):
                ids.extend([x for x in v if isinstance(x, str)])

    # 2) common nested keys
    nested_paths = [
        ["execution_metadata", "job_id"],
        ["execution_metadata", "jobId"],
        ["proof", "execution_metadata", "job_id"],
        ["proof", "execution_metadata", "jobId"],
        ["ibm", "job_id"],
        ["ibm", "jobId"],
    ]
    for p in nested_paths:
        v = deep_get(obj, p)
        if isinstance(v, str):
            ids.append(v)

    # 3) scan strings everywhere (robust)
    all_text = "\n".join(ensure_text(v) for v in walk_all_values(obj) if isinstance(v, (str, int, float)))
    ids.extend(extract_job_ids_from_text(all_text))

    # normalize + dedupe
    out: List[str] = []
    seen: Set[str] = set()
    for x in ids:
        if not isinstance(x, str):
            continue
        x = x.strip()
        if not x:
            continue
        xlow = x.lower()
        if not xlow.startswith(LIKELY_JOB_PREFIX):
            continue
        if xlow not in seen:
            seen.add(xlow)
            out.append(xlow)
    return out


def extract_backend(obj: Any) -> Optional[str]:
    # common locations
    candidates = [
        ["backend"],
        ["hardware", "backend"],
        ["execution_metadata", "backend"],
        ["proof", "execution_metadata", "backend"],
        ["ibm", "backend"],
        ["summary", "backend"],
    ]
    for p in candidates:
        v = deep_get(obj, p)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # try scan for "ibm_" backend strings
    for v in walk_all_values(obj):
        if isinstance(v, str) and v.startswith("ibm_"):
            return v
    return None


def extract_shots(obj: Any) -> Optional[int]:
    candidates = [
        ["shots"],
        ["summary", "shots"],
        ["execution_metadata", "shots"],
        ["proof", "execution_metadata", "shots"],
        ["ibm", "shots"],
    ]
    for p in candidates:
        v = deep_get(obj, p)
        if isinstance(v, int) and v > 0:
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)

    # fallback: search for {"shots": N} in nested runs list
    if isinstance(obj, dict):
        for k in ("runs", "results", "jobs", "executions"):
            v = obj.get(k)
            if isinstance(v, list):
                for item in v:
                    vv = deep_get(item, ["shots"])
                    if isinstance(vv, int) and vv > 0:
                        return vv
    return None


def extract_timestamp(obj: Any) -> Optional[str]:
    # common keys
    if isinstance(obj, dict):
        for k in ("timestamp", "created_utc", "created", "time", "date"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()

    # nested
    for p in (["summary", "timestamp"], ["metadata", "timestamp"], ["execution_metadata", "timestamp"]):
        v = deep_get(obj, p)
        if isinstance(v, str) and v.strip():
            return v.strip()

    return None


def detect_evidence_group_id(obj: Any, fallback: str) -> str:
    if isinstance(obj, dict):
        v = obj.get("evidence_group_id")
        if isinstance(v, str) and v.strip():
            return v.strip()
    return fallback


# ---------------------------
# Files + outputs
# ---------------------------

def build_entry(file_path: Path, base_dir: Path, obj: Optional[Dict[str, Any]], git_commit: str) -> Dict[str, Any]:
    rel = str(file_path.relative_to(base_dir))
    entry: Dict[str, Any] = {
        "file": rel,
        "sha256": sha256_file(file_path),
        "size_bytes": file_path.stat().st_size,
        "git_commit": git_commit,
    }

    # Assign group id
    entry["evidence_group_id"] = detect_evidence_group_id(obj, file_path.stem) if obj else file_path.stem

    # Extract metadata if JSON
    if obj:
        backend = extract_backend(obj)
        ts = extract_timestamp(obj)
        shots = extract_shots(obj)
        job_ids = extract_job_ids(obj)

        if backend:
            entry["backend"] = backend
        if ts:
            entry["timestamp"] = ts
        if shots is not None:
            entry["shots"] = shots
        if job_ids:
            entry["job_ids"] = job_ids

    return entry


def write_sha256sums(base_dir: Path, entries: List[Dict[str, Any]]) -> None:
    lines = [f"{e['sha256']}  {e['file']}" for e in sorted(entries, key=lambda x: x["file"])]
    (base_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_index_md(base_dir: Path, manifest: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Evidence Index — docs/evidence")
    lines.append("")
    lines.append(f"- Generated: {manifest['generated_utc']}")
    lines.append(f"- Git commit: `{manifest['git_commit']}`")
    lines.append("")
    lines.append("## Files")
    lines.append("")
    for e in sorted(manifest["evidence_sets"], key=lambda x: x["file"]):
        lines.append(f"### {e['file']}")
        lines.append(f"- SHA256: `{e['sha256']}`")
        if "backend" in e:
            lines.append(f"- Backend: `{e['backend']}`")
        if "shots" in e:
            lines.append(f"- Shots: `{e['shots']}`")
        if "timestamp" in e:
            lines.append(f"- Timestamp: `{e['timestamp']}`")
        if "job_ids" in e:
            lines.append(f"- Job IDs ({len(e['job_ids'])}):")
            for jid in e["job_ids"]:
                lines.append(f"  - `{jid}`")
        lines.append(f"- evidence_group_id: `{e['evidence_group_id']}`")
        lines.append("")
    (base_dir / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def write_warnings_md(base_dir: Path, manifest: Dict[str, Any]) -> None:
    sets = manifest["evidence_sets"]

    # Collect job IDs from JSON evidence
    json_job_ids: Set[str] = set()
    dashboard_job_ids: Set[str] = set()

    # Identify dashboard markdowns and extract job ids from their text
    for e in sets:
        f = e["file"]
        p = base_dir / f
        if f.lower().endswith(".md"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            ids = extract_job_ids_from_text(text)
            # heuristically, treat "dashboard evidence" as any md containing "Dashboard" or "IBM Quantum Dashboard"
            if "dashboard" in text.lower():
                dashboard_job_ids.update(ids)

        if f.lower().endswith(".json") and "job_ids" in e:
            json_job_ids.update([jid.lower() for jid in e["job_ids"]])

    # Find mismatches: dashboard ids not in json ids
    missing_in_json = sorted([jid for jid in dashboard_job_ids if jid.lower() not in json_job_ids])

    # Lint for missing fields
    missing_backend = [e["file"] for e in sets if e["file"].lower().endswith(".json") and "backend" not in e]
    missing_shots = [e["file"] for e in sets if e["file"].lower().endswith(".json") and "shots" not in e]
    missing_timestamp = [e["file"] for e in sets if e["file"].lower().endswith(".json") and "timestamp" not in e]
    missing_job_ids = [e["file"] for e in sets if e["file"].lower().endswith(".json") and "job_ids" not in e]

    lines: List[str] = []
    lines.append("# Evidence Warnings / Consistency Report")
    lines.append("")
    lines.append(f"- Generated: {manifest['generated_utc']}")
    lines.append(f"- Git commit: `{manifest['git_commit']}`")
    lines.append("")

    if missing_in_json:
        lines.append("## Dashboard job IDs not found in JSON evidence")
        lines.append("These job IDs appear in dashboard markdown(s) but were not found in any JSON evidence file:")
        lines.append("")
        for jid in missing_in_json:
            lines.append(f"- `{jid}`")
        lines.append("")
        lines.append("Recommendation: add `evidence_group_id` and ensure the dashboard MD references the same group + job_id as the JSON artifact.")
        lines.append("")

    def section(title: str, items: List[str]) -> None:
        if not items:
            return
        lines.append(f"## {title}")
        for it in sorted(items):
            lines.append(f"- {it}")
        lines.append("")

    section("JSON evidence missing `backend` field", missing_backend)
    section("JSON evidence missing `shots` field", missing_shots)
    section("JSON evidence missing `timestamp` field", missing_timestamp)
    section("JSON evidence missing `job_ids` field", missing_job_ids)

    if len(lines) <= 6:
        lines.append("No issues detected by current heuristics. ✅")
        lines.append("")

    (base_dir / "WARNINGS.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default="docs/evidence", help="Evidence folder")
    ap.add_argument("--write-index", action="store_true", help="Also write INDEX.md")
    ap.add_argument("--no-warnings", action="store_true", help="Do not write WARNINGS.md")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent
    base_dir = (repo_root / args.evidence).resolve()
    if not base_dir.exists():
        print(f"Evidence directory not found: {base_dir}", file=os.sys.stderr)
        return 2

    git_commit = try_git_commit(repo_root)
    generated_utc = dt.datetime.now(dt.timezone.utc).isoformat()

    entries: List[Dict[str, Any]] = []

    candidates = sorted(
        [p for p in base_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".json", ".md")]
    )

    for p in candidates:
        obj = None
        if p.suffix.lower() == ".json":
            try:
                obj0 = json.loads(p.read_text(encoding="utf-8"))
                obj = obj0 if isinstance(obj0, dict) else {"_root": obj0}
            except Exception:
                obj = None

        entry = build_entry(p, base_dir, obj, git_commit)
        entries.append(entry)

    manifest: Dict[str, Any] = {
        "schema_version": 2,
        "generated_utc": generated_utc,
        "git_commit": git_commit,
        "evidence_sets": entries,
    }

    (base_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    write_sha256sums(base_dir, entries)
    if args.write_index:
        write_index_md(base_dir, manifest)
    if not args.no_warnings:
        write_warnings_md(base_dir, manifest)

    print(f"Wrote: {base_dir / 'manifest.json'}")
    print(f"Wrote: {base_dir / 'SHA256SUMS'}")
    if args.write_index:
        print(f"Wrote: {base_dir / 'INDEX.md'}")
    if not args.no_warnings:
        print(f"Wrote: {base_dir / 'WARNINGS.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())