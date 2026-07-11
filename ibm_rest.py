"""Submit jobs to IBM Quantum through the raw REST API.

The Qiskit runtime client's instance-discovery fails for some brand-new IBM
Cloud accounts (it cannot enumerate the instance even though the instance works).
The REST API accepts the instance CRN directly and works fine, so we talk to it
straight. Credentials come from the environment, never from this repo:

    export QHRC_IBM_TOKEN=...    # IBM Cloud API key
    export QHRC_IBM_CRN=...      # quantum instance CRN

This mirrors what SamplerV2 does under the hood: transpile to the backend's
basis, submit a "sampler" primitive job, poll, and read the quasi-distributions.
"""
from __future__ import annotations

import os
import time

import requests

BASE = "https://quantum.cloud.ibm.com/api/v1"


def _iam_token(api_key: str) -> str:
    r = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
        headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def _headers():
    tok = os.environ["QHRC_IBM_TOKEN"]
    crn = os.environ["QHRC_IBM_CRN"]
    return {"Authorization": f"Bearer {_iam_token(tok)}", "Service-CRN": crn}


def backend_config(name: str, headers=None):
    headers = headers or _headers()
    r = requests.get(f"{BASE}/backends/{name}/configuration", headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def least_busy(headers=None):
    headers = headers or _headers()
    devices = requests.get(f"{BASE}/backends", headers=headers, timeout=30).json()["devices"]
    best, best_q = None, 1e18
    for d in devices:
        st = requests.get(f"{BASE}/backends/{d}/status", headers=headers, timeout=30).json()
        if st.get("state") and st.get("length_queue", 1e18) < best_q:
            best, best_q = d, st.get("length_queue", 0)
    return best, best_q


def submit_sampler(qpy_circuit_b64, backend_name, shots, headers=None):
    """Submit one transpiled circuit as a SamplerV2 job. Returns job_id."""
    headers = headers or _headers()
    body = {
        "program_id": "sampler",
        "backend": backend_name,
        "hub": None, "group": None, "project": None,
        "params": {
            "pubs": [[qpy_circuit_b64]],
            "version": 2,
            "shots": shots,
        },
    }
    r = requests.post(f"{BASE}/jobs", headers={**headers, "Content-Type": "application/json"},
                      json=body, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"submit failed {r.status_code}: {r.text[:400]}")
    return r.json()["id"]


def wait_job(job_id, headers=None, poll=15, timeout_s=3600):
    headers = headers or _headers()
    waited = 0
    while waited < timeout_s:
        r = requests.get(f"{BASE}/jobs/{job_id}", headers=headers, timeout=30).json()
        status = r.get("status") or r.get("state", {}).get("status")
        if status in ("Completed", "COMPLETED", "Done", "DONE"):
            return "done"
        if status in ("Failed", "FAILED", "Cancelled", "CANCELLED"):
            raise RuntimeError(f"job {job_id} ended: {status} :: {str(r)[:300]}")
        time.sleep(poll)
        waited += poll
    raise TimeoutError(f"job {job_id} did not finish in {timeout_s}s")


def job_results(job_id, headers=None):
    headers = headers or _headers()
    r = requests.get(f"{BASE}/jobs/{job_id}/results", headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()
