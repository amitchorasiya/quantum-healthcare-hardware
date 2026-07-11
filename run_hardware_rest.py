"""Run the three showcase circuits on a real IBM QPU via the REST API.

Why REST and not the Qiskit client: this new IBM Cloud account's API key works
with the instance directly but the client's instance-discovery returns empty, so
SamplerV2 refuses to submit. The REST endpoints accept the instance CRN and work,
so we use them.

Reads the exact + simulator numbers already in results/comparison.json and fills
in the hardware fields with real device data. Nothing is fabricated: if a job
fails or times out, that circuit's hardware entry stays null and we say so.

    export QHRC_IBM_TOKEN=...  QHRC_IBM_CRN=...
    python run_hardware_rest.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from qiskit import qasm3, transpile
from qiskit.transpiler import CouplingMap

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import ibm_rest  # noqa: E402
from ibm_experiments.circuits import all_circuits  # noqa: E402

RESULTS = ROOT / "results"
SHOTS = 4096


def counts_to_probs(counts, n_qubits):
    total = sum(counts.values()) or 1
    probs = np.zeros(2 ** n_qubits)
    for bitstr, c in counts.items():
        idx = int(str(bitstr).replace(" ", ""), 2)
        probs[idx] = c / total
    return probs


def tvd(p, q):
    return float(0.5 * np.sum(np.abs(p - q)))


def hellinger_fidelity(p, q):
    return float(np.sum(np.sqrt(p * q)) ** 2)


def _top(probs, k=4):
    n = int(np.log2(len(probs)))
    idx = np.argsort(probs)[::-1][:k]
    return [{"bits": format(int(i), f"0{n}b"), "p": round(float(probs[i]), 4)} for i in idx]


def extract_counts(results_json, n_qubits):
    """Pull a counts dict from a SamplerV2 REST result payload."""
    # SamplerV2 results nest under results[0].data.<creg>.samples or .counts
    res = results_json
    if isinstance(res, dict) and "results" in res:
        res = res["results"]
    pub = res[0]
    data = pub.get("data", pub)
    # find the classical register field
    for key, val in data.items():
        if isinstance(val, dict) and ("counts" in val or "samples" in val):
            if "counts" in val:
                # counts may be hex-keyed
                out = {}
                for k, c in val["counts"].items():
                    kk = int(k, 16) if str(k).startswith("0x") else int(k, 2)
                    out[format(kk, f"0{n_qubits}b")] = c
                return out
            samples = val["samples"]
            out = {}
            for s in samples:
                kk = int(s, 16) if str(s).startswith("0x") else int(str(s), 2)
                b = format(kk, f"0{n_qubits}b")
                out[b] = out.get(b, 0) + 1
            return out
    raise ValueError(f"cannot find counts in result: {str(results_json)[:200]}")


def main():
    comp_path = RESULTS / "comparison.json"
    comparison = json.loads(comp_path.read_text())

    H = ibm_rest._headers()
    backend_name, queue = ibm_rest.least_busy(H)
    print(f"backend: {backend_name} (queue {queue})")
    cfg = ibm_rest.backend_config(backend_name, H)
    basis, cmap = cfg["basis_gates"], CouplingMap(cfg["coupling_map"])

    circuits = all_circuits()
    # 1) submit all three up front so they queue together
    jobs = {}
    for name, (qc, _meta) in circuits.items():
        qc.name = "c"  # QASM3 identifiers cannot start with a capital letter
        tqc = transpile(qc, basis_gates=basis, coupling_map=cmap, optimization_level=1)
        q3 = qasm3.dumps(tqc)
        jid = ibm_rest.submit_sampler(q3, backend_name, SHOTS, H)
        jobs[name] = jid
        print(f"  submitted {name} -> job {jid}")

    # 2) collect results, fill in hardware fields
    for rec in comparison["circuits"]:
        name = rec["circuit"]
        jid = jobs.get(name)
        if not jid:
            continue
        n = rec["n_qubits"]
        p_exact = np.array(rec["_dists"]["exact"])
        try:
            print(f"  waiting on {name} ({jid})...")
            ibm_rest.wait_job(jid, H, poll=20, timeout_s=7200)
            res = ibm_rest.job_results(jid, H)
            counts = extract_counts(res, n)
            p_hw = counts_to_probs(counts, n)
            rec["hardware"] = {
                "backend": backend_name, "job_id": jid,
                "tvd_vs_exact": round(tvd(p_exact, p_hw), 4),
                "fidelity_vs_exact": round(hellinger_fidelity(p_exact, p_hw), 4),
                "top": _top(p_hw),
            }
            rec["_dists"]["hw"] = p_hw.tolist()
            h = rec["hardware"]
            print(f"    {name}: hw TVD={h['tvd_vs_exact']} fid={h['fidelity_vs_exact']}")
        except Exception as exc:  # noqa: BLE001
            print(f"    {name} hardware run failed: {type(exc).__name__}: {str(exc)[:200]}")
            rec["hardware"] = None

    comparison["hardware_backend"] = backend_name
    comp_path.write_text(json.dumps(comparison, indent=2))
    print(f"\nsaved -> {comp_path}")


if __name__ == "__main__":
    main()
