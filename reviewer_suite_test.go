package main

/*
reviewer_suite_test.go

Single-file reviewer suite that consolidates the repo's key Go regression tests and
microbenchmarks into one place.

How to run (from repo root):
  go test -v -run TestReviewerSuite ./...
  go test -v -run TestReviewerSuite
  go test -bench BenchmarkReviewerSuite -run ^$

Notes:
- This file imports the same internal packages as the original test files:
  github.com/hydraresearch/qzkp/src/classical
  github.com/hydraresearch/qzkp/src/security
- It intentionally focuses on "engineering security goals" (transcript non-inclusion,
  heuristic leakage detection, soundness mapping), not a formal cryptographic proof.
*/

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"math"
	"testing"
	"time"

	"github.com/hydraresearch/qzkp/src/classical"
	"github.com/hydraresearch/qzkp/src/security"
)

func TestReviewerSuite(t *testing.T) {
	t.Run("InformationLeakageDetection", testInformationLeakageDetection)
	t.Run("SecureProtocolNoDirectInclusion", testSecureProtocolNoDirectInclusion)
	t.Run("SoundnessMappingSanity", testSoundnessMappingSanity)
	t.Run("RNGVariabilitySanity", testRNGVariabilitySanity)
}

// --- Core tests (condensed) ---

func testInformationLeakageDetection(t *testing.T) {
	// Distinctive vectors that naive "serialization" schemes often leak.
	testVectors := [][]byte{
		[]byte("AAAAAAAAAAAAAAAA"),
		[]byte("0123456789ABCDEF"),
		[]byte("FEDCBA9876543210"),
		[]byte("A5A5A5A5A5A5A5A5"),
	}

	key := []byte("security-test-key-32bytes-length")
	leakageDetected := false

	for _, v := range testVectors {
		commitment := classical.CreateCommitment(v, key)

		// Heuristic leakage checks:
		// 1) raw vector should not appear in JSON
		b, _ := json.Marshal(commitment)
		if bytes.Contains(b, v) {
			leakageDetected = true
		}

		// 2) hex form should not appear either
		hx := []byte(hex.EncodeToString(v))
		if bytes.Contains(bytes.ToLower(b), bytes.ToLower(hx)) {
			leakageDetected = true
		}
	}

	if leakageDetected {
		t.Fatalf("Leakage detected by heuristic transcript scan (sanity check failed)")
	}
}

func testSecureProtocolNoDirectInclusion(t *testing.T) {
	// Generates a proof and ensures the proof transcript doesn't contain a naive
	// serialization of the underlying witness bytes.
	witness := make([]byte, 32)
	if _, err := rand.Read(witness); err != nil {
		t.Fatalf("rand.Read: %v", err)
	}

	sec := security.NewSecureQuantumZKP(256)
	commitment, err := sec.Commit(witness)
	if err != nil {
		t.Fatalf("Commit: %v", err)
	}
	proof, err := sec.Prove(commitment)
	if err != nil {
		t.Fatalf("Prove: %v", err)
	}

	// Verify should succeed for honest path
	ok, err := sec.Verify(commitment, proof)
	if err != nil {
		t.Fatalf("Verify err: %v", err)
	}
	if !ok {
		t.Fatalf("Verify returned false for honest flow")
	}

	// Heuristic: proof JSON must not contain witness bytes directly.
	pb, _ := json.Marshal(proof)
	if bytes.Contains(pb, witness) || bytes.Contains(bytes.ToLower(pb), []byte(hex.EncodeToString(witness))) {
		t.Fatalf("Proof appears to include witness bytes directly (non-inclusion goal failed)")
	}
}

func testSoundnessMappingSanity(t *testing.T) {
	// Maps "security level" bits -> challenge count k and checks 2^-k
	cases := []struct {
		bits int
		k    int
	}{
		{32, 32},
		{64, 64},
		{80, 80},
		{128, 128},
		{256, 256},
	}

	for _, c := range cases {
		k := security.ChallengesForSecurityBits(c.bits)
		if k != c.k {
			t.Fatalf("security bits %d: expected k=%d, got %d", c.bits, c.k, k)
		}
		// soundness bound: 2^-k
		want := math.Pow(0.5, float64(k))
		got := security.SoundnessErrorForChallenges(k)
		if math.Abs(got-want) > 1e-18 {
			t.Fatalf("k=%d: expected soundness=%g, got %g", k, want, got)
		}
	}
}

func testRNGVariabilitySanity(t *testing.T) {
	// Very simple "should differ" check across runs.
	a := make([]byte, 32)
	b := make([]byte, 32)
	if _, err := rand.Read(a); err != nil {
		t.Fatalf("rand.Read: %v", err)
	}
	if _, err := rand.Read(b); err != nil {
		t.Fatalf("rand.Read: %v", err)
	}
	if bytes.Equal(a, b) {
		t.Fatalf("unexpected: RNG produced identical 32-byte outputs")
	}
}

// --- Benchmarks (condensed) ---

func BenchmarkReviewerSuite(b *testing.B) {
	b.Run("CommitProveVerify_256", benchCommitProveVerify256)
}

func benchCommitProveVerify256(b *testing.B) {
	sec := security.NewSecureQuantumZKP(256)
	witness := make([]byte, 32)
	_, _ = rand.Read(witness)

	commitment, _ := sec.Commit(witness)
	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		proof, err := sec.Prove(commitment)
		if err != nil {
			b.Fatalf("Prove: %v", err)
		}
		ok, err := sec.Verify(commitment, proof)
		if err != nil || !ok {
			b.Fatalf("Verify failed: ok=%v err=%v", ok, err)
		}
	}
	b.StopTimer()
	_ = time.Now() // keep import honest on some toolchains
}
