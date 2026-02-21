---
geometry: margin=1in
fontsize: 11pt
linestretch: 1.15
header-includes:
  - \usepackage{titlesec}
  - \titlespacing{\section}{0pt}{12pt plus 4pt minus 2pt}{6pt plus 2pt minus 2pt}
  - \titlespacing{\subsection}{0pt}{10pt plus 3pt minus 2pt}{4pt plus 2pt minus 2pt}
  - \usepackage{needspace}
---

# Secure Quantum Zero-Knowledge Proofs: Implementation, Security Goals, and Empirical Leakage Evaluation

**Author:** Nicolas Cloutier  
**ORCID:** 0009-0008-5289-5324  
**Affiliation:** GrillCheese AI (formerly: Hydra Research & Labs)  
**Code:** https://github.com/Grillcheese-AI/qzkp-academic
**Date:** May 24th, 2025 (Revised: Feb 21st, 2026)

## Abstract

We present an end-to-end reference implementation of a quantum zero-knowledge proof (QZKP) *prototype* together with a structured security analysis focused on transcript leakage in practical encodings of quantum witnesses. The system supports configurable soundness levels (32–256 bits) via repeated challenges and combines standard cryptographic components for integrity and aggregation, including hash-based commitments (SHA-256 / BLAKE3), Merkle-tree aggregation, and post-quantum authentication using ML-DSA (derived from CRYSTALS-Dilithium).

Our core contribution is a construction we call *probabilistic entanglement*, designed to enable verification of a quantum-dependent relation while limiting what a verifier can infer about the underlying witness from protocol transcripts. We state explicit threat models and assumptions, provide a simulator-based zero-knowledge claim under computational indistinguishability, and supply empirical leakage tests demonstrating that naive transcript designs can reveal witness structure whereas the proposed design avoids direct inclusion of state-vector components.

We report experimental executions on IBM Quantum hardware and characterize proof sizes and runtimes across security settings. Finally, we release the full source code and test suite to support reproducibility, regression testing, and cryptographic review.

**Keywords:** quantum cryptography, zero-knowledge proofs, post-quantum cryptography, transcript leakage, soundness amplification

\needspace{4\baselineskip}

## 1. Introduction

Quantum zero-knowledge proofs (QZKP) aim to let a prover convince a verifier of knowledge of a quantum witness without revealing the witness itself. While the theory of quantum ZK is well-developed, practical implementations can fail to meet ZK goals due to transcript design choices, serialization, or inadvertent disclosure of witness-related data. This work contributes a reference implementation and a security-oriented evaluation framework centered on *information leakage through transcripts*.

### 1.1 Problem Statement

Designing a practical QZKP prototype raises recurring issues:

1. **Transcript Leakage**: avoiding direct or indirect inclusion of witness data in proofs/transcripts.
2. **Commitment Design**: binding and hiding commitments with clear assumptions and digest-length guidance.
3. **Soundness Parameterization**: explicit mapping between challenge repetitions and soundness error.
4. **Post-Quantum Authentication**: compatibility with standardized PQC signatures (e.g., ML-DSA).

### 1.2 Contributions

- **Implementation**: an end-to-end Go prototype with tests and reproducible artifacts.
- **Leakage Evaluation**: automated tests to detect transcript inclusion of witness components in naive designs and validate a “no-direct-inclusion” design goal in the secure variant.
- **Security Goals & Claims**: clearly stated assumptions, threat model, and a computational zero-knowledge claim with a simulator definition.
- **Empirical Results**: hardware execution artifacts and performance characterization across security levels.

\needspace{4\baselineskip}

## 2. Background and Definitions

### 2.1 Quantum Zero-Knowledge (QZK)

We follow the standard completeness/soundness/zero-knowledge structure. Let $x$ be an instance and $w$ a witness (quantum or classical, depending on the relation). The protocol defines an interactive view for any (possibly malicious) verifier $V^\*$.

- **Completeness:** honest prover convinces honest verifier for valid $(x,w)$.
- **Soundness:** cheating prover convinces honest verifier on invalid $x \not\in L$ only with small probability.
- **Zero-Knowledge:** the verifier’s view can be simulated without access to $w$.

### 2.2 Post-Quantum Authentication

For authentication and integrity we use post-quantum signatures (ML-DSA / CRYSTALS-Dilithium) and hash-based commitments (SHA-256/BLAKE3). Security depends on standard assumptions and parameter choices, especially commitment digest length.

\newpage

## 3. Threat Model and Security Claims

### 3.1 Threat Model (Summary)

We consider a malicious verifier $V^\*$ that can adaptively choose challenges and record full transcripts. The verifier is quantum polynomial-time unless stated otherwise. We *do not* claim information-theoretic ZK; our ZK claim is computational unless explicitly strengthened.

### 3.2 Zero-Knowledge

**Theorem 1 (Computational Zero-Knowledge).**  
For any quantum polynomial-time verifier $V^\*$, there exists a quantum polynomial-time simulator $S$ such that for all valid instances $x$:

$$
\mathrm{View}_{V^\*}(P,V^\*)(x) \approx_c S(x),
$$

where $\approx_c$ denotes computational indistinguishability.

*Proof sketch.* The simulator reproduces transcript distributions by sampling challenges and generating commitments/responses consistent with verification checks without embedding witness-specific amplitudes into the transcript. The full proof is provided in Appendix B with explicit assumptions.

### 3.3 Soundness

**Theorem 2 (Soundness with Repetition).**  
For any cheating prover $P^\*$ and any false statement $x \not\in L$:

$$
\Pr[\langle P^\*,V\rangle(x)=1] \le \varepsilon(k),
$$

where $k$ is the number of independent challenges. For binary challenges, $\varepsilon(k) \le 2^{-k}$.

This yields a direct mapping between “security level” and challenge count.

\needspace{4\baselineskip}

## 4. Probabilistic Entanglement Framework (Design Overview)

We introduce a design intended to prevent transcripts from containing raw witness amplitudes while still enabling verification of a relation.

### 4.1 High-Level Construction

1. **Encoding:** Map input data to a normalized state $|\psi_d\rangle$.
2. **Proof State:** Build an entangled construction that couples verification operations to $|\psi_d\rangle$ without serializing $|\psi_d\rangle$.
3. **Commit-and-Challenge:** Commit to measurement outcomes and randomness, then answer challenges.
4. **Verify:** Verification checks commitments and response consistency.

### 4.2 Notes on Observables

If two measurements are intended to be jointly measurable without disturbing one another, the relevant property is *commutation* (compatibility), not “orthogonality”. We use commutation relations to state when validity checks can be performed without targeting secret-bearing observables.

\newpage

## 5. Leakage Evaluation Methodology and Results

### 5.1 What We Test

We treat “zero leakage” in this paper as a **concrete engineering goal**: transcripts must not directly include witness state-vector components or trivially reconstructible amplitude encodings.

We implement tests that attempt:
- direct amplitude matching (sanity check),
- reconstruction heuristics against naive serialization,
- statistical checks over large randomized test sets.

### 5.2 Results Summary

We report that naive transcript designs can leak witness structure, while the secure variant avoids direct witness inclusion according to the implemented test suite. We emphasize that these tests are evidence of *non-inclusion* and resistance to specific reconstruction strategies, not a standalone cryptographic proof.

\needspace{4\baselineskip}

## 6. Performance Characterization

We report proof size and runtime measurements as a function of $k$ (challenge count / soundness level). In our implementation, proof generation and verification scale approximately linearly in $k$; verification is designed to remain low-latency in practice.

## 7. Conclusion

We provide a reproducible QZKP prototype, a structured threat model, simulator-based computational ZK claims under explicit assumptions, and an empirical leakage evaluation framework aimed at catching common implementation failures. This work is intended as a foundation for continued cryptographic review and future strengthening of formal guarantees.

## References

[1] Watrous, J. (2009). Zero-knowledge against quantum attacks. SIAM Journal on Computing, 39(1), 25–58.  
[2] Kobayashi, H. (2003). Non-interactive quantum perfect and statistical zero-knowledge. ISAAC.  
[3] NIST. FIPS 204 (ML-DSA). (for post-quantum signatures)  
[4] O'Connor et al. (2020). BLAKE3. ePrint 2020/1143.  
[5] Merkle, R. (1987). A digital signature based on a conventional encryption function.

---

## Appendix A: Reproducibility

- Hardware and simulator artifacts are published as JSON alongside the code repository.
- IBM Quantum experiments include backend, shots, and job metadata where available.

## Appendix B: Proof Details (Outline)

- Assumptions and reduction targets
- Simulator construction
- Soundness amplification proof
- Commitment security discussion (digest length, collision/preimage assumptions)