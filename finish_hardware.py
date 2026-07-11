"""Finisher: wait for IBM access, run the real hardware jobs, refresh artifacts.

Polls the IBM service until the trial instance propagates, then runs the full
comparison on a real QPU, regenerates plots, and prints the numbers. Confluence
and git updates are done by the caller (they need MCP / gh), but this leaves
results/comparison.json and results/plots/ fully updated with real data.

    python finish_hardware.py            # poll up to ~2h, then run
    python finish_hardware.py --once     # try once, exit
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def reachable():
    from qiskit_ibm_runtime import QiskitRuntimeService
    try:
        svc = QiskitRuntimeService(name="qhrc")
        reals = svc.backends(simulator=False, operational=True)
        return len(reals) > 0
    except Exception:
        return False


def main(once=False, poll_seconds=120, max_hours=2):
    deadline = None if once else max_hours * 3600
    waited = 0
    while True:
        if reachable():
            print("IBM hardware reachable. Running real comparison...")
            import run_comparison
            import make_plots
            run_comparison.main(sim_only=False)
            make_plots.main()
            print("Done. results/comparison.json and plots updated with real hardware data.")
            return True
        if once:
            print("Not reachable yet.")
            return False
        if deadline is not None and waited >= deadline:
            print(f"Gave up after {max_hours}h. Instance still not propagated.")
            return False
        print(f"Not reachable yet. Waited {waited // 60} min. Retrying in {poll_seconds}s...")
        time.sleep(poll_seconds)
        waited += poll_seconds


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    main(once=ap.parse_args().once)
