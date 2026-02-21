# Threat Model and Assumptions

## Adversary
We consider a malicious verifier V* that:
- sees full protocol transcripts,
- adaptively selects challenges,
- is quantum polynomial-time (QPT) unless stated otherwise.

## Goals
- Computational zero-knowledge: transcripts are indistinguishable from a simulator output.
- Soundness: a prover without the witness succeeds with probability ≤ 2^{-k} (binary challenge repetition).

## Non-goals (explicit)
- We do not claim information-theoretic ZK.
- We do not claim universal post-quantum security for every component beyond standard assumptions.
- We do not claim “production readiness” without external review.

## Assumptions
- Hash-based commitments rely on standard assumptions and adequate digest length.
- PQ authentication relies on ML-DSA security.
- Randomness is generated from cryptographically secure sources.