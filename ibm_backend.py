"""Connect to IBM Quantum, or fall back to a local simulator.

Credentials live in ~/.qiskit (saved with QiskitRuntimeService.save_account under
the name "qhrc"). Nothing secret is stored in this repo. If no account or no
network is available, callers can still run the exact and shot-based simulators.

Set QHRC_BACKEND to force a specific real backend name. Otherwise we pick the
least busy real device.
"""
from __future__ import annotations

import os

ACCOUNT_NAME = "qhrc"


def get_service():
    """Return a live QiskitRuntimeService, or None if unavailable."""
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
        return QiskitRuntimeService(name=ACCOUNT_NAME)
    except Exception as exc:  # noqa: BLE001
        print(f"[ibm_backend] no IBM service: {type(exc).__name__}: {str(exc)[:150]}")
        return None


def get_real_backend(service=None, min_qubits: int = 5):
    """Return (backend, name) for the least busy real device, or (None, None)."""
    service = service or get_service()
    if service is None:
        return None, None
    forced = os.environ.get("QHRC_BACKEND")
    try:
        if forced:
            b = service.backend(forced)
        else:
            b = service.least_busy(simulator=False, operational=True, min_num_qubits=min_qubits)
        return b, b.name
    except Exception as exc:  # noqa: BLE001
        print(f"[ibm_backend] cannot get real backend: {type(exc).__name__}: {str(exc)[:150]}")
        return None, None


def hardware_available() -> bool:
    b, _ = get_real_backend()
    return b is not None
