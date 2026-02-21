#!/usr/bin/env python3
import os
import sys

def main() -> int:
    token = os.environ.get("IBM_QUANTUM_TOKEN") or os.environ.get("QISKIT_IBM_TOKEN")
    if not token:
        print("IBM creds not found (IBM_QUANTUM_TOKEN/QISKIT_IBM_TOKEN). Skipping.")
        return 0

    try:
        from qiskit import QuantumCircuit
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
    except Exception as e:
        print(f"IBM runtime deps missing: {e}. Skipping.")
        return 0

    # Connect
    service = QiskitRuntimeService(channel="ibm_quantum", token=token)
    backend = service.least_busy(operational=True, simulator=False)
    print("Backend:", backend.name)

    # Tiny Bell circuit
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])

    sampler = Sampler(backend=backend)
    job = sampler.run([qc], shots=1000)
    print("Job ID:", job.job_id())
    result = job.result()
    # result structure varies; we keep it simple:
    print("Result received OK.")
    return 0

if __name__ == "__main__":
    sys.exit(main())