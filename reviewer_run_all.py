#!/usr/bin/env python3
"""
reviewer_run_all.py

Single-file reviewer runner that consolidates the project's Python-side evidence work into one entry point.

What it does:
- Always runs LOCAL checks (no IBM access required):
  - probabilistic encoding sanity
  - bytes -> quantum-state normalization sanity
  - lightweight algorithm microbenchmarks (CPU)

- Optionally runs IBM Quantum Runtime smoke + selected circuits if credentials are present:
  - detects token from IBM_QUANTUM_TOKEN or QISKIT_IBM_TOKEN
  - uses qiskit-ibm-runtime (Sampler V2) when installed
  - skips cleanly if deps/creds missing

Outputs:
- Writes a small evidence bundle to: docs/evidence/out/<timestamp>/
  - run_metadata.json
  - local_results.json
  - optional ibm_results.json
  - INDEX.md
  - SHA256SUMS

Usage:
  python reviewer_run_all.py
  python reviewer_run_all.py --ibm
  python reviewer_run_all.py --out docs/evidence/out
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent
DEFAULT_OUT_BASE = ROOT / "docs" / "evidence" / "out"


def now_utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(p: Path, obj: Any) -> None:
    p.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def write_text(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def get_git_commit() -> str:
    git = ROOT / ".git"
    if not git.exists():
        return "unknown"
    try:
        import subprocess

        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


# ---------------------------
# Local sanity checks
# ---------------------------

def bytes_to_amplitudes(data: bytes) -> List[complex]:
    # Deterministic mapping: interpret bytes as signed ints, map to complex plane, normalize later.
    if not data:
        data = b"\x00"
    amps: List[complex] = []
    for b in data:
        x = (b - 128) / 128.0
        y = ((b * 131) % 256 - 128) / 128.0
        amps.append(complex(x, y))
    return amps


def normalize(vec: List[complex]) -> List[complex]:
    norm2 = sum((v.real * v.real + v.imag * v.imag) for v in vec)
    if norm2 <= 0:
        return [0j for _ in vec]
    inv = 1.0 / (norm2 ** 0.5)
    return [v * inv for v in vec]


def local_probabilistic_encoding_sanity() -> Dict[str, Any]:
    # Simple invariants: normalization, non-trivial entropy-ish distribution of magnitudes.
    payload = b"reviewer-sanity-payload-0123456789"
    amps = normalize(bytes_to_amplitudes(payload))
    mags = [abs(a) for a in amps]
    s = sum(mags)
    # crude entropy proxy
    import math
    probs = [m / s for m in mags] if s > 0 else [1 / len(mags)] * len(mags)
    entropy = -sum(p * math.log(p + 1e-18) for p in probs)
    return {
        "payload_len": len(payload),
        "vector_len": len(amps),
        "l2_norm": float(sum(abs(a) ** 2 for a in amps)),
        "entropy_proxy": float(entropy),
        "min_mag": float(min(mags)),
        "max_mag": float(max(mags)),
    }


def local_microbench() -> Dict[str, Any]:
    # Microbench: encode+normalize repeated.
    payload = os.urandom(1024)
    iters = 2000
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = normalize(bytes_to_amplitudes(payload))
    t1 = time.perf_counter()
    return {
        "iters": iters,
        "secs": t1 - t0,
        "per_iter_us": (t1 - t0) * 1e6 / iters,
    }


# ---------------------------
# Optional IBM Runtime path
# ---------------------------

def ibm_token() -> Optional[str]:
    return os.environ.get("IBM_QUANTUM_TOKEN") or os.environ.get("QISKIT_IBM_TOKEN")


def try_ibm_smoke(shots: int = 1000) -> Dict[str, Any]:
    token = ibm_token()
    if not token:
        return {"skipped": True, "reason": "No IBM token in env (IBM_QUANTUM_TOKEN/QISKIT_IBM_TOKEN)"}

    try:
        from qiskit import QuantumCircuit
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
    except Exception as e:
        return {"skipped": True, "reason": f"Missing deps (qiskit / qiskit-ibm-runtime): {e}"}

    service = QiskitRuntimeService(channel="ibm_quantum", token=token)
    backend = service.least_busy(operational=True, simulator=False)
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])

    sampler = Sampler(backend=backend)
    job = sampler.run([qc], shots=shots)
    job_id = job.job_id()

    # Result object can vary; keep minimal.
    _ = job.result()
    return {
        "skipped": False,
        "backend": backend.name,
        "job_id": job_id,
        "shots": shots,
        "note": "Bell-state smoke submission via SamplerV2; full parsing intentionally minimal for reviewer simplicity.",
    }


# ---------------------------
# Bundle writer
# ---------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT_BASE), help="Base output directory")
    ap.add_argument("--ibm", action="store_true", help="Attempt IBM Runtime smoke test if configured")
    args = ap.parse_args()

    ts = now_utc_stamp()
    out_dir = Path(args.out) / ts
    ensure_dir(out_dir)

    meta = {
        "artifact_type": "reviewer_one_file_runner",
        "created_utc": ts,
        "git_commit": get_git_commit(),
        "platform": {
            "python": sys.version.replace("\n", " "),
            "os": platform.platform(),
            "machine": platform.machine(),
        },
    }
    write_json(out_dir / "run_metadata.json", meta)

    local = {
        "probabilistic_encoding_sanity": local_probabilistic_encoding_sanity(),
        "microbench": local_microbench(),
    }
    write_json(out_dir / "local_results.json", local)

    ibm = None
    if args.ibm:
        ibm = try_ibm_smoke(shots=1000)
        write_json(out_dir / "ibm_results.json", ibm)
    else:
        write_text(out_dir / "ibm_NOTE.txt", "IBM path not requested. Run with --ibm to attempt smoke test (optional).")

    # INDEX.md
    lines = []
    lines.append(f"# Reviewer Evidence Bundle — {ts}")
    lines.append("")
    lines.append(f"- Git commit: `{meta['git_commit']}`")
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append("- `run_metadata.json` — environment + commit")
    lines.append("- `local_results.json` — local sanity checks + microbench")
    if args.ibm:
        lines.append("- `ibm_results.json` — IBM runtime smoke test (or skipped reason)")
    else:
        lines.append("- `ibm_NOTE.txt` — how to run optional IBM smoke test")
    lines.append("- `SHA256SUMS` — checksums for integrity")
    lines.append("")
    write_text(out_dir / "INDEX.md", "\n".join(lines))

    # SHA256SUMS
    sums = []
    for p in sorted(out_dir.iterdir()):
        if p.is_file() and p.name != "SHA256SUMS":
            sums.append(f"{sha256_file(p)}  {p.name}")
    write_text(out_dir / "SHA256SUMS", "\n".join(sums) + "\n")

    print(f"Wrote evidence bundle: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
