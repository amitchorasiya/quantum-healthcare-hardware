"""One-time IBM Quantum account setup, plus a connection check.

Run once with your token and instance CRN. It saves them to ~/.qiskit (outside
this repo) under the account name "qhrc". After that, run_comparison.py finds
the account on its own.

    python setup_ibm.py --token YOUR_API_KEY --crn "crn:v1:bluemix:..."
    python setup_ibm.py --check          # just test the connection

Get your API key and instance CRN from https://quantum.cloud.ibm.com
(dashboard -> API keys, and the instance CRN under Instances).
"""
from __future__ import annotations

import argparse


def save(token: str, crn: str):
    from qiskit_ibm_runtime import QiskitRuntimeService
    QiskitRuntimeService.save_account(
        channel="ibm_quantum_platform", token=token, instance=crn,
        name="qhrc", overwrite=True)
    print("saved account 'qhrc' to ~/.qiskit")


def check():
    from qiskit_ibm_runtime import QiskitRuntimeService
    svc = QiskitRuntimeService(name="qhrc")
    reals = svc.backends(simulator=False, operational=True)
    print("real backends:", [b.name for b in reals])
    if reals:
        print("least busy:", svc.least_busy(simulator=False, operational=True).name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--token")
    ap.add_argument("--crn")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.token and args.crn:
        save(args.token, args.crn)
    if args.check or not (args.token and args.crn):
        check()
