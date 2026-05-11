from __future__ import annotations

# Soubor vytvari referencni vystupy pro realne loterie.
# Neslouzi ke kalibraci, jen ke srovnani v praci.

import csv
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt


def load_reference(path: str | Path = "data/real_lottery_reference.csv") -> List[Dict[str, str]]:
    # nacte CSV s realnymi loteriemi pro srovnani
    with Path(path).open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def export_reference_outputs(output_dir: str | Path = "output_bp/reference") -> None:
    # exportuje referencni data a grafy pro porovnani modelu s realitou
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = load_reference()
    with (out / "real_lottery_reference.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    plot_jackpot_odds(rows, out / "real_lottery_jackpot_odds.png")
    plot_expected_jackpots(rows, out / "real_lottery_expected_jackpots.png")


def plot_jackpot_odds(rows, output_path: Path) -> None:
    # sloupcovy graf srovnavajici sance na jackpot u ruznych loterii
    names = [r["name"] for r in rows]
    odds = [float(r["jackpot_odds"]) for r in rows]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(names, odds)
    ax.set_xscale("log")
    ax.set_xlabel("Jackpot odds: 1 ku N (logaritmicka osa)")
    ax.set_title("Srovnani jackpotove pravdepodobnosti modelu a realnych loterii")
    for i, v in enumerate(odds):
        ax.text(v * 1.08, i, f"1:{v:,.0f}".replace(",", " "), va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_expected_jackpots(rows, output_path: Path) -> None:
    # kolik jackpotu bychom ocekavali pri ruznem poctu prodanych tiketu
    ticket_counts = [1_000_000, 5_000_000, 10_000_000, 50_000_000]
    fig, ax = plt.subplots(figsize=(10, 5))
    for r in rows:
        odds = float(r["jackpot_odds"])
        y = [n / odds for n in ticket_counts]
        ax.plot(ticket_counts, y, marker="o", label=r["name"])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Pocet prodanych tiketu")
    ax.set_ylabel("Ocekavany pocet jackpotu")
    ax.set_title("Ocekavany pocet jackpotu podle velikosti trhu")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
