# Quantum Zero-Knowledge Proof (QZKP) Prototype

**Author:** Nicolas Cloutier (ORCID: 0009-0008-5289-5324)  
**Organization:** GrillCheese AI  
**Repository:** https://github.com/grillcheese-ai/qzkp

## What this is

This repository provides an end-to-end **reference implementation (prototype)** of a quantum zero-knowledge proof (QZKP)-style protocol plus a **leakage evaluation test suite** designed to catch common implementation failures (e.g., accidental serialization of witness/state-vector data).

## Critical note

This repository contains **two implementations**:
1) `QuantumZKP` (insecure / educational): demonstrates how transcripts can leak witness structure.
2) `SecureQuantumZKP` (secure-by-design goals): avoids direct inclusion of witness amplitudes in transcripts and uses cryptographic commitments + PQ authentication.

**Important:** The “secure” variant is a prototype with explicit assumptions and threat model (see `docs/threat_model.md`). It is intended for research and review.

## Security goals

- Simulator-based **computational** zero-knowledge claim under stated assumptions.
- Soundness via challenge repetition: soundness error ≤ 2^{-k}.
- Transcript design goal: no direct witness/state-vector inclusion in proofs.
- Post-quantum authentication using **ML-DSA** (derived from CRYSTALS-Dilithium).

## Reproducibility (reviewers)

Local (no IBM access required):
```bash
go test -v -run TestReviewerSuite
python reviewer_run_all.py
python make_evidence_manifest.py --write-index



## Quick start

```bash
go test ./... -v
go test ./... -run TestInformationLeakageAnalysis -v
go test ./... -bench=. 


