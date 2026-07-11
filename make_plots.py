"""Charts for the simulator-vs-hardware comparison.

Reads results/comparison.json. Draws, per circuit, the output distribution for
exact / simulator / hardware side by side. Also draws a summary bar of accuracy
(fidelity vs exact) across circuits. Hardware bars appear only once a real run
has filled them in.

    python make_plots.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PLOTS = RESULTS / "plots"

EXACT_C = "#4C4CFF"
SIM_C = "#00B8A9"
HW_C = "#F6416C"
plt.rcParams.update({"figure.dpi": 130, "font.size": 10, "axes.grid": True,
                     "grid.alpha": 0.25, "axes.spines.top": False, "axes.spines.right": False})


def load():
    return json.loads((RESULTS / "comparison.json").read_text())


def plot_distributions(data):
    circuits = data["circuits"]
    fig, axes = plt.subplots(1, len(circuits), figsize=(5 * len(circuits), 4))
    if len(circuits) == 1:
        axes = [axes]
    for ax, rec in zip(axes, circuits):
        d = rec["_dists"]
        n = rec["n_qubits"]
        labels = [format(i, f"0{n}b") for i in range(2 ** n)]
        x = np.arange(2 ** n)
        exact = np.array(d["exact"])
        sim = np.array(d["sim"])
        w = 0.27
        ax.bar(x - w, exact, w, label="exact", color=EXACT_C)
        ax.bar(x, sim, w, label="simulator", color=SIM_C)
        if d.get("hw") is not None:
            ax.bar(x + w, np.array(d["hw"]), w, label="hardware", color=HW_C)
        ax.set_title(rec["circuit"])
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=90, fontsize=6)
        ax.set_ylabel("probability")
        ax.legend(fontsize=8)
    fig.suptitle("Same circuit, three machines: exact vs simulator vs real quantum hardware", y=1.03)
    fig.tight_layout()
    fig.savefig(PLOTS / "distributions.png", bbox_inches="tight")
    plt.close(fig)


def plot_accuracy(data):
    circuits = data["circuits"]
    names = [c["circuit"] for c in circuits]
    sim_fid = [c["sim_shots"]["fidelity_vs_exact"] for c in circuits]
    hw_fid = [c["hardware"]["fidelity_vs_exact"] if c["hardware"] else None for c in circuits]
    x = np.arange(len(names))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(x - w / 2, sim_fid, w, label="simulator", color=SIM_C)
    if all(v is not None for v in hw_fid):
        ax.bar(x + w / 2, hw_fid, w, label="hardware", color=HW_C)
    ax.axhline(1.0, ls="--", color="gray", lw=1, label="perfect (1.0)")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15)
    ax.set_ylabel("fidelity vs exact answer (1.0 = perfect)")
    ax.set_ylim(0, 1.05)
    ax.set_title("How close each machine gets to the exact answer")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(PLOTS / "accuracy.png")
    plt.close(fig)


def main():
    PLOTS.mkdir(parents=True, exist_ok=True)
    data = load()
    plot_distributions(data)
    plot_accuracy(data)
    print(f"wrote plots -> {PLOTS}")


if __name__ == "__main__":
    main()
