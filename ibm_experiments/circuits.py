"""Three small showcase circuits, one per original experiment.

Each circuit is tiny on purpose so it fits the free IBM trial budget and runs in
a single job. Every circuit ends in a measurement so we can compare output
distributions across: exact statevector, shot-based simulator, and real QPU.

The originals swept sizes and trained models. Here we freeze one representative
circuit per experiment (the interesting one) and ask a sharper question: how far
does real hardware drift from the exact answer?
"""
from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import zz_feature_map


N_QUBITS = 4  # small enough for hardware, big enough to be interesting


# --------------------------------------------------------------------------
# Exp 1 showcase: a single quantum-kernel fidelity overlap.
# Kernel value K(x,y) = |<psi(x)|psi(y)>|^2 = P(measure all zeros) of the
# compute-uncompute circuit U(y)^dagger U(x). On a perfect machine that
# probability IS the kernel entry. Noise pushes it around, which corrupts the
# kernel matrix. This circuit shows exactly how much.
# --------------------------------------------------------------------------
def kernel_overlap_circuit(seed: int = 0) -> QuantumCircuit:
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1, 1, size=N_QUBITS)
    y = rng.uniform(-1, 1, size=N_QUBITS)
    fmap = zz_feature_map(feature_dimension=N_QUBITS, reps=1, entanglement="linear")
    ux = fmap.assign_parameters(x)
    uy = fmap.assign_parameters(y)
    qc = QuantumCircuit(N_QUBITS)
    qc.compose(ux, inplace=True)
    qc.compose(uy.inverse(), inplace=True)
    qc.measure_all()
    return qc


# --------------------------------------------------------------------------
# Exp 2 showcase: the optimal QAOA state for a tiny nurse-scheduling QUBO.
# We hard-code a good (beta, gamma) so the circuit is fixed and small. The
# output should concentrate on the optimal bitstring. Noise smears that peak.
# --------------------------------------------------------------------------
def qaoa_schedule_circuit() -> tuple[QuantumCircuit, dict]:
    # 4-variable QUBO: reward turning bits on, penalize conflicting pairs.
    # Chosen so the optimum is a clear, single bitstring.
    n = N_QUBITS
    # Ising terms tuned for a clean single-peak optimum at 1010.
    h = np.array([-1.0, 0.8, -1.0, 0.8])
    J = {(0, 1): 0.9, (1, 2): 0.9, (2, 3): 0.9}
    beta, gamma = 0.6, 0.8

    qc = QuantumCircuit(n)
    qc.h(range(n))                       # uniform superposition
    # cost layer
    for i in range(n):
        qc.rz(2 * gamma * h[i], i)
    for (i, j), w in J.items():
        qc.cx(i, j)
        qc.rz(2 * gamma * w, j)
        qc.cx(i, j)
    # mixer layer
    for i in range(n):
        qc.rx(2 * beta, i)
    qc.measure_all()

    # Brute-force the true optimum of this QUBO for scoring.
    def energy(bits):
        z = 1 - 2 * np.array(bits)
        e = sum(h[i] * z[i] for i in range(n))
        e += sum(w * z[i] * z[j] for (i, j), w in J.items())
        return e
    import itertools
    best = min(itertools.product([0, 1], repeat=n), key=energy)
    best_str = "".join(str(b) for b in reversed(best))  # qiskit bit order
    return qc, {"optimal_bitstring": best_str, "h": h.tolist(), "J": {f"{k}": v for k, v in J.items()}}


# --------------------------------------------------------------------------
# Exp 3 showcase: a small Quantum Circuit Born Machine with fixed, pre-set
# weights. Its measured distribution is the "generated" sample. We compare the
# hardware distribution to the exact one to see how noise distorts what the
# generator produces.
# --------------------------------------------------------------------------
def qcbm_circuit(seed: int = 0) -> QuantumCircuit:
    rng = np.random.default_rng(seed)
    n = N_QUBITS
    layers = 2
    weights = rng.uniform(0, 2 * np.pi, size=(layers, n, 2))
    qc = QuantumCircuit(n)
    for L in range(layers):
        for w in range(n):
            qc.ry(weights[L, w, 0], w)
            qc.rz(weights[L, w, 1], w)
        for w in range(n):
            qc.cx(w, (w + 1) % n)
    qc.measure_all()
    return qc


def all_circuits():
    """Return {name: (circuit, meta)} for the three showcases."""
    qaoa_qc, qaoa_meta = qaoa_schedule_circuit()
    return {
        "kernel_overlap": (kernel_overlap_circuit(seed=0),
                           {"note": "P(all-zeros) is the quantum-kernel entry K(x,y)"}),
        "qaoa_schedule": (qaoa_qc, qaoa_meta),
        "qcbm_generator": (qcbm_circuit(seed=0),
                           {"note": "measured distribution = the generated sample"}),
    }
