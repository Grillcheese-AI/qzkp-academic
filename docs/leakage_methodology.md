# Leakage Evaluation Methodology

## What we test
- Direct witness inclusion (e.g., amplitude/probability bytes appearing in transcripts)
- Naive serialization failures (state vectors embedded in JSON / logs)
- Reconstruction heuristics against the insecure baseline

## What we do NOT claim
- This is not a formal proof of zero-knowledge.
- Passing tests does not guarantee security against all adversaries.

## Why it’s still useful
- Prevents common engineering mistakes
- Provides regression tests for changes
- Makes “security goals” concrete and measurable