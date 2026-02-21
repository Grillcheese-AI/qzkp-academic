# Executive Summary — QZKP Prototype and Leakage Evaluation

This project provides:
- A reproducible QZKP-style prototype implementation (Go)
- A leakage evaluation framework intended to detect transcript disclosure risks
- Performance and proof-size characterization across soundness settings (32–256 bits via repetition)

## Why it matters

Practical implementations can accidentally leak witness structure through transcripts (e.g., by embedding or serializing amplitudes/probabilities). This repo includes an intentionally insecure baseline to demonstrate failure modes and a secure-by-design variant that aims to prevent direct witness inclusion and supports structured cryptographic review.

## Security posture

- Zero-knowledge claim: **computational** ZK under stated assumptions (see threat model).
- Soundness: amplification by repetition, with error bounded by 2^{-k}.
- Commitments: hash-based commitments (SHA-256/BLAKE3) with security dependent on digest length and standard assumptions.
- Authentication: post-quantum signatures using ML-DSA (CRYSTALS-Dilithium).

## What “0% leakage” means here

Our tests demonstrate “no direct inclusion” of witness amplitudes in transcripts and resistance to specific reconstruction heuristics used in the test suite. These tests are evidence and regression protection; they do not replace a formal cryptographic proof.

## Next steps

- External cryptographic review
- Strengthen proof structure and reduce assumptions
- Expand leakage adversary models (e.g., learning-based reconstruction)