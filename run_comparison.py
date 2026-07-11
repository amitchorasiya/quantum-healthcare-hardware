"""Run each showcase circuit three ways and measure how far hardware drifts.

Three runs per circuit:
  1. exact      - statevector, the ground truth (no sampling, no noise)
  2. sim_shots  - local sampler with the same shot count (sampling noise only)
  3. hardware   - a real IBM QPU (sampling noise + real device noise)

We save every distribution plus accuracy metrics (total variation distance and
Hellinger fidelity vs the exact truth). Simulator runs happen now. Hardware runs
happen when an IBM backend is reachable; until then the hardware fields stay
null and the script says so. Nothing is fabricated.

    python run_comparison.py --sim-only      # simulator side now
    python run_comparison.py                 # add hardware when reachable
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from qiskit import transpile
from qiskit.quantum_info import Statevector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from ibm_experiments.circuits import all_circuits  # noqa: E402
from ibm_backend import get_real_backend, get_service  # noqa: E402

SHOTS = 4096
RESULTS = ROOT / "results"


# ---- distribution helpers -------------------------------------------------
def counts_to_probs(counts, n_qubits):
    total = sum(counts.values())
    probs = np.zeros(2 ** n_qubits)
    for bitstr, c in counts.items():
        idx = int(bitstr.replace(" ", ""), 2)
        probs[idx] = c / total
    return probs


def exact_probs(circuit):
    """Exact output distribution via statevector (strip the measurement)."""
    qc = circuit.remove_final_measurements(inplace=False)
    sv = Statevector(qc)
    return np.abs(sv.data) ** 2


def tvd(p, q):
    return float(0.5 * np.sum(np.abs(p - q)))


def hellinger_fidelity(p, q):
    return float(np.sum(np.sqrt(p * q)) ** 2)


# ---- runners --------------------------------------------------------------
def run_sim_shots(circuit, shots=SHOTS):
    from qiskit_aer import AerSimulator
    sim = AerSimulator()
    tqc = transpile(circuit, sim)
    result = sim.run(tqc, shots=shots).result()
    return result.get_counts()


def run_hardware(circuit, backend, shots=SHOTS):
    from qiskit_ibm_runtime import SamplerV2
    tqc = transpile(circuit, backend, optimization_level=1)
    sampler = SamplerV2(mode=backend)
    job = sampler.run([tqc], shots=shots)
    print(f"    submitted job {job.job_id()} to {backend.name}; waiting...")
    res = job.result()
    # SamplerV2: pull the single classical register's counts.
    pub = res[0]
    counts = pub.data.meas.get_counts()
    return counts, job.job_id()


def analyze(name, circuit, meta, backend):
    n = circuit.num_qubits
    p_exact = exact_probs(circuit)

    sim_counts = run_sim_shots(circuit)
    p_sim = counts_to_probs(sim_counts, n)

    record = {
        "circuit": name,
        "n_qubits": n,
        "shots": SHOTS,
        "meta": meta,
        "exact_top": _top(p_exact),
        "sim_shots": {
            "tvd_vs_exact": round(tvd(p_exact, p_sim), 4),
            "fidelity_vs_exact": round(hellinger_fidelity(p_exact, p_sim), 4),
            "top": _top(p_sim),
        },
        "hardware": None,
    }

    if backend is not None:
        counts, job_id = run_hardware(circuit, backend)
        p_hw = counts_to_probs(counts, n)
        record["hardware"] = {
            "backend": backend.name,
            "job_id": job_id,
            "tvd_vs_exact": round(tvd(p_exact, p_hw), 4),
            "fidelity_vs_exact": round(hellinger_fidelity(p_exact, p_hw), 4),
            "top": _top(p_hw),
        }
        # keep raw distributions for plotting
        record["_dists"] = {"exact": p_exact.tolist(), "sim": p_sim.tolist(), "hw": p_hw.tolist()}
    else:
        record["_dists"] = {"exact": p_exact.tolist(), "sim": p_sim.tolist(), "hw": None}
    return record


def _top(probs, k=4):
    n = int(np.log2(len(probs)))
    idx = np.argsort(probs)[::-1][:k]
    return [{"bits": format(int(i), f"0{n}b"), "p": round(float(probs[i]), 4)} for i in idx]


def main(sim_only=False):
    RESULTS.mkdir(parents=True, exist_ok=True)
    backend = None
    if not sim_only:
        service = get_service()
        backend, name = get_real_backend(service)
        if backend is None:
            print("No IBM hardware reachable yet. Running simulator side only.")
        else:
            print(f"Using real backend: {name}")

    out = {"shots": SHOTS, "circuits": []}
    for name, (circuit, meta) in all_circuits().items():
        print(f"== {name} ==")
        rec = analyze(name, circuit, meta, backend)
        out["circuits"].append(rec)
        s = rec["sim_shots"]
        line = f"   sim: TVD={s['tvd_vs_exact']} fid={s['fidelity_vs_exact']}"
        if rec["hardware"]:
            h = rec["hardware"]
            line += f" | hw({h['backend']}): TVD={h['tvd_vs_exact']} fid={h['fidelity_vs_exact']}"
        print(line)

    path = RESULTS / "comparison.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"\nsaved -> {path}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-only", action="store_true")
    main(**{"sim_only": ap.parse_args().sim_only})
