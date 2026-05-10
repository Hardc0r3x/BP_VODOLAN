from __future__ import annotations

from collections import Counter, defaultdict
from math import comb
from pathlib import Path
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from config import Config
from statistiky import SberStatistik


# globalni nastaveni grafu - bez ramecku nahore a vpravo, mrizka polopruhledna
plt.rcParams.update({
    "figure.dpi": 120,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "font.family": "DejaVu Sans",
})

# barvy pro jednotlive strategie - pouzivam vsude stejne
STRATEGY_COLORS = {
    "Nahodna": "#16a34a",
    "FixedCisla": "#2563eb",
    "Martingale": "#dc2626",
    "HotCold_hot": "#d97706",
    "HotCold_cold": "#0891b2",
}
PALETTE = list(STRATEGY_COLORS.values())

def _strategy_linestyle(name: str) -> str:
    return STRATEGY_LINESTYLES.get(name, "-")

# ruzne styly car aby se daly rozlisit i v cernobilem tisku
STRATEGY_LINESTYLES = {
    "Nahodna": "-",
    "FixedCisla": "--",
    "Martingale": "-",
    "HotCold_hot": "-.",
    "HotCold_cold": ":",
}

def _save(fig: plt.Figure, path: str | Path, dpi: int = 180) -> None:
    # ulozit graf do souboru
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  Ulozen: {path}")


def _strategy_color(name: str) -> str:
    return STRATEGY_COLORS.get(name, "#666666")


def plot_strategy_roi(stats: SberStatistik, output_path: str | Path) -> None:
    # boxplot distribuce ROI pro kazdou strategii
    strategy_rois: Dict[str, list[float]] = defaultdict(list)
    for run in stats.runs:
        for agent in run.agent_summaries:
            strategy_rois[agent["strategy"]].append(float(agent["roi"]))

    labels = sorted(strategy_rois)
    data = [strategy_rois[label] for label in labels]

    fig, ax = plt.subplots(figsize=(max(9, len(labels) * 2.0), 5))
    bp = ax.boxplot(
        data, patch_artist=True, showfliers=True,
        flierprops={"marker": ".", "markersize": 3, "alpha": 0.25},
        medianprops={"color": "white", "linewidth": 2},
    )
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels)
    for patch, label in zip(bp["boxes"], labels):
        patch.set_facecolor(_strategy_color(label))
        patch.set_alpha(0.78)

    # orez os aby outliery nezkreslily graf
    all_rois = [value for values in data for value in values]
    if all_rois:
        p1, p99 = np.percentile(all_rois, [1, 99])
        ax.set_ylim(max(-110, p1 - 10), min(500, p99 + 25))

    ax.axhline(0, color="black", linestyle="--", linewidth=1, label="ROI = 0 %")
    ax.set_title("Distribuce ROI podle sazkove strategie")
    ax.set_xlabel("Strategie")
    ax.set_ylabel("ROI (%)")
    ax.tick_params(axis="x", rotation=15)
    ax.legend(loc="lower right")
    _save(fig, output_path)


def plot_strategy_cumulative_loss(stats: SberStatistik, output_path: str | Path) -> None:
    # graf kumulativniho zisku/ztraty pres kola pro kazdou strategii
    max_rounds = max((len(run.round_data) for run in stats.runs), default=0)
    if max_rounds == 0:
        return

    strat_runs: Dict[str, list[list[float]]] = defaultdict(list)

    for run in stats.runs:
        run_rounds = len(run.round_data)
        by_strategy: Dict[str, list[list[float]]] = defaultdict(list)

        for agent in run.agent_summaries:
            cumulative = 0.0
            seq = []

            for record in agent.get("history", []):
                cumulative += float(record.get("prize", 0)) - float(record.get("cost", 0))
                seq.append(cumulative)

            if not seq:
                seq = [0.0] * run_rounds

            # doplnit na plny pocet kol kdyz hrac skoncil driv
            if len(seq) < run_rounds:
                seq = seq + [seq[-1]] * (run_rounds - len(seq))

            if len(seq) > run_rounds:
                seq = seq[:run_rounds]

            by_strategy[agent["strategy"]].append(seq)

        for strategy, sequences in by_strategy.items():
            mat = np.array(sequences, dtype=float)
            strat_runs[strategy].append(np.mean(mat, axis=0).tolist())

    fig, ax = plt.subplots(figsize=(11, 5))

    for strategy in sorted(strat_runs):
        curves = strat_runs[strategy]
        fixed_curves = []

        for curve in curves:
            if len(curve) < max_rounds:
                curve = curve + [curve[-1]] * (max_rounds - len(curve))
            if len(curve) > max_rounds:
                curve = curve[:max_rounds]
            fixed_curves.append(curve)

        mat = np.array(fixed_curves, dtype=float)
        mean_curve = np.mean(mat, axis=0)

        ax.plot(
            np.arange(1, len(mean_curve) + 1),
            mean_curve,
            label=strategy,
            color=_strategy_color(strategy),
            linestyle=_strategy_linestyle(strategy),
            linewidth=2,
            alpha=0.9,
        )

    ax.axhline(0, color="black", linestyle="--", linewidth=1)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.set_title("Prumerny kumulativni vysledek vsech hracu podle strategie")
    ax.set_xlabel("Kolo")
    ax.set_ylabel("Kumulativni zisk/ztrata (Kc)")
    ax.legend()
    _save(fig, output_path)


def plot_strategy_bankruptcy(stats: SberStatistik, output_path: str | Path) -> None:
    # sloupcovy graf miry bankrotu podle strategie
    data = stats.get_strategy_stats()
    labels = sorted(data)
    values = [data[label]["bankruptcy_rate_pct"] for label in labels]
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, values, color=[_strategy_color(label) for label in labels], alpha=0.82)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + max(values + [1]) * 0.02, f"{value:.1f} %", ha="center", fontsize=8)
    ax.set_title("Mira bankrotu hracu podle strategie")
    ax.set_xlabel("Strategie")
    ax.set_ylabel("Bankrot hracu (%)")
    ax.tick_params(axis="x", rotation=15)
    _save(fig, output_path)


def plot_agent_survival(stats: SberStatistik, output_path: str | Path) -> None:
    # jak rychle ubyvaji aktivni hraci v prubehu simulace
    max_rounds = max((len(run.round_data) for run in stats.runs), default=0)
    if max_rounds == 0:
        return

    active_counts: Dict[str, np.ndarray] = defaultdict(lambda: np.zeros(max_rounds))
    total_counts: Dict[str, int] = defaultdict(int)

    for run in stats.runs:
        for agent in run.agent_summaries:
            strategy = agent["strategy"]
            total_counts[strategy] += 1

            for r in range(min(int(agent["rounds_played"]), max_rounds)):
                active_counts[strategy][r] += 1

    fig, ax = plt.subplots(figsize=(11, 5))
    rounds = np.arange(1, max_rounds + 1)

    for strategy in sorted(active_counts):
        pct = active_counts[strategy] / max(total_counts[strategy], 1) * 100
        ax.plot(
            rounds,
            pct,
            label=strategy,
            color=_strategy_color(strategy),
            linestyle=_strategy_linestyle(strategy),
            linewidth=2,
            alpha=0.9,
        )

    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f} %"))
    ax.set_title("Podil aktivnich agentu v prubehu simulace")
    ax.set_xlabel("Kolo")
    ax.set_ylabel("Aktivni agenti (%)")
    ax.legend()
    _save(fig, output_path)


def plot_operator_capital_distribution(stats: SberStatistik, output_path: str | Path) -> None:
    # histogram konecneho kapitalu provozovatele pres vsechny MC behy
    finals = np.array([run.operator_summary["final_capital"] for run in stats.runs], dtype=float)
    initial = float(stats.runs[0].operator_summary["initial_capital"])
    mean = float(np.mean(finals))
    p5 = float(np.percentile(finals, 5))
    bankrupt = sum(1 for run in stats.runs if run.operator_summary["bankrupt"])
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.hist(finals, bins=50, color=PALETTE[0], alpha=0.78, edgecolor="none")
    ax.axvline(initial, color="black", linestyle="--", linewidth=1.5, label=f"Pocatecni kapital {initial / 1e6:.1f} mil. Kc")
    ax.axvline(mean, color=PALETTE[1], linewidth=2, label=f"Prumer {mean / 1e6:.2f} mil. Kc")
    ax.axvline(p5, color=PALETTE[2], linestyle=":", linewidth=2, label=f"5. percentil {p5 / 1e6:.2f} mil. Kc")
    if bankrupt:
        ax.text(0.02, 0.92, f"Bankrot: {bankrupt}/{len(stats.runs)} behu", transform=ax.transAxes)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x / 1e6:.2f} M"))
    ax.set_title("Rozdeleni konecneho kapitalu provozovatele")
    ax.set_xlabel("Konecny kapital (Kc)")
    ax.set_ylabel("Pocet MC behu")
    ax.legend()
    _save(fig, output_path)


def plot_capital_timeseries(stats: SberStatistik, output_path: str | Path) -> None:
    # vyvoj kapitalu provozovatele v case - prumer a 5.-95. percentil
    max_rounds = max((len(run.round_data) for run in stats.runs), default=0)
    if max_rounds == 0:
        return
    mat = np.full((len(stats.runs), max_rounds), np.nan)
    for i, run in enumerate(stats.runs):
        for j, row in enumerate(run.round_data):
            mat[i, j] = row["operator_capital"]
    rounds = np.arange(1, max_rounds + 1)
    mean = np.nanmean(mat, axis=0)
    p5 = np.nanpercentile(mat, 5, axis=0)
    p95 = np.nanpercentile(mat, 95, axis=0)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.fill_between(rounds, p5, p95, color=PALETTE[0], alpha=0.12, label="5.-95. percentil")
    ax.plot(rounds, mean, color=PALETTE[0], linewidth=2.4, label="Prumer")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x / 1e6:.2f} M"))
    ax.set_title("Vyvoj kapitalu provozovatele v case")
    ax.set_xlabel("Kolo")
    ax.set_ylabel("Kapital provozovatele (Kc)")
    ax.legend()
    _save(fig, output_path)


def plot_operator_cashflow(stats: SberStatistik, output_path: str | Path) -> None:
    # prumerne prijmy a vydaje provozovatele po kolech
    max_rounds = max((len(run.round_data) for run in stats.runs), default=0)
    if max_rounds == 0:
        return
    rev = np.full((len(stats.runs), max_rounds), np.nan)
    pay = np.full((len(stats.runs), max_rounds), np.nan)
    for i, run in enumerate(stats.runs):
        for j, row in enumerate(run.round_data):
            rev[i, j] = row["revenue"]
            pay[i, j] = row["payouts"]
    rounds = np.arange(1, max_rounds + 1)
    avg_rev = np.nanmean(rev, axis=0)
    avg_pay = np.nanmean(pay, axis=0)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(rounds, avg_rev, color=PALETTE[1], linewidth=2, label="Prijmy z tiketu")
    ax.plot(rounds, avg_pay, color=PALETTE[2], linewidth=2, label="Vyplaty vyher")
    ax.plot(rounds, avg_rev - avg_pay, color="black", linestyle=":", linewidth=2, label="Rozdil")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.set_title("Prumerny cashflow provozovatele")
    ax.set_xlabel("Kolo")
    ax.set_ylabel("Kc za kolo")
    ax.legend()
    _save(fig, output_path)


def plot_match_probability(stats: SberStatistik, config: Config, output_path: str | Path) -> None:
    # srovnani teoretickych a simulovanych pravdepodobnosti vyher
    matches = [3, 4, 5, 6]
    theoretical = [config.match_probability(k) * 100 for k in matches]
    empirical = [stats.get_prize_stats(config)[k]["pct_actual"] for k in matches]
    labels = ["3 shody", "4 shody", "5 shod", "6 shod"]
    x = np.arange(len(matches))
    width = 0.35
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(x - width / 2, theoretical, width, label="Teoreticka", color=PALETTE[0], alpha=0.82)
    ax.bar(x + width / 2, empirical, width, label="Simulovana", color=PALETTE[1], alpha=0.82)
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f"{y:.4g} %"))
    ax.set_title("Pravdepodobnosti vyhernich trid: simulace vs. kombinatorika")
    ax.set_xlabel("Vyherni trida")
    ax.set_ylabel("Pravdepodobnost (%)")
    ax.legend()
    _save(fig, output_path)


def plot_rtp_distribution(stats: SberStatistik, config: Config, output_path: str | Path) -> None:
    # histogram RTP pres vsechny MC behy
    rtps = []
    for run in stats.runs:
        rev = float(run.operator_summary.get("total_revenue", 0) or 0)
        pay = float(run.operator_summary.get("total_payouts", 0) or 0)
        if rev > 0:
            rtps.append(pay / rev * 100)
    if not rtps:
        return
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(rtps, bins=40, color=PALETTE[0], alpha=0.78, edgecolor="none")
    ax.axvline(config.theoretical_rtp(), color="black", linestyle="--", linewidth=2, label=f"Teoreticke RTP {config.theoretical_rtp():.1f} %")
    ax.axvline(np.mean(rtps), color=PALETTE[1], linewidth=2, label=f"Prumer {np.mean(rtps):.1f} %")
    ax.set_title("Distribuce Return-to-Player pres MC behy")
    ax.set_xlabel("RTP za jeden beh (%)")
    ax.set_ylabel("Pocet MC behu")
    ax.legend()
    _save(fig, output_path)


def plot_mc_convergence(stats: SberStatistik, config: Config, output_path: str | Path) -> None:
    # graf jak prubezny prumer RTP konverguje s rostoucim poctem behu
    running = stats.get_convergence_stats()["running_mean_rtp"]
    if not running:
        return
    x = np.arange(1, len(running) + 1)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x, running, linewidth=1.8, label="Prubezny prumer RTP")
    ax.axhline(config.theoretical_rtp(), color="black", linestyle="--", linewidth=1.5, label=f"Teoreticke RTP {config.theoretical_rtp():.2f} %")
    ax.set_title("Konvergence prumerneho RTP v Monte Carlo simulaci")
    ax.set_xlabel("Pocet MC behu")
    ax.set_ylabel("RTP (%)")
    ax.legend()
    _save(fig, output_path)


def plot_number_frequencies(stats: SberStatistik, config: Config, output_path: str | Path) -> None:
    # frekvence tazenych cisel - kontrola ze PRNG generuje rovnomerne
    counts: Counter[int] = Counter()
    for run in stats.runs:
        for row in run.round_data:
            counts.update(row.get("drawn", []))
    numbers = list(range(1, config.num_balls + 1))
    freqs = np.array([counts.get(n, 0) / max(len(stats.runs), 1) for n in numbers], dtype=float)
    expected = config.num_rounds * config.draw_size / config.num_balls
    fig, ax = plt.subplots(figsize=(13, 4.5))
    ax.bar(numbers, freqs, color=PALETTE[0], alpha=0.75, width=0.88)
    ax.axhline(expected, color=PALETTE[2], linestyle="--", linewidth=1.8, label=f"Ocekavani {expected:.1f}x/beh")
    ax.set_xlim(0.5, config.num_balls + 0.5)
    ax.set_title("Frekvence tazenych cisel - kontrola uniformity PRNG")
    ax.set_xlabel("Cislo")
    ax.set_ylabel("Prumerna cetnost na beh")
    ax.legend()
    _save(fig, output_path)


def plot_jackpot_expectation(stats: SberStatistik, config: Config, output_path: str | Path) -> None:
    # ukazuje kolik jackpotu bychom ocekavali pri ruznem poctu MC behu
    tickets_per_run = stats.total_tickets() / max(stats.num_runs, 1)
    runs = np.array([50, 100, 500, 1_000, 2_000, 5_000, 10_000])
    expected = runs * tickets_per_run * config.jackpot_probability()
    p_no = np.exp(-expected) * 100
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(runs, expected, marker="o", color=PALETTE[0], label="Ocekavany pocet jackpotu")
    ax1.set_xscale("log")
    ax1.set_xlabel("Pocet MC behu")
    ax1.set_ylabel("Ocekavany pocet jackpotu")
    ax1.axhline(1, color="gray", linestyle="--", linewidth=1)
    ax2 = ax1.twinx()
    ax2.plot(runs, p_no, marker="s", color="black", linestyle=":", label="P(zadny jackpot)")
    ax2.set_ylabel("Pravdepodobnost zadneho jackpotu (%)")
    ax2.set_ylim(0, 105)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
    ax1.set_title("Vliv poctu MC behu na pozorovani vzacneho jackpotu")
    _save(fig, output_path)


def plot_scenario_comparison(results: Dict[str, Dict[str, Any]], output_path: str | Path) -> None:
    # trojity graf srovnavajici scenare - bankrot, kapital, marze
    names = list(results.keys())
    bankrupt = [results[name]["operator"]["bankruptcy_rate_pct"] for name in names]
    capital = [results[name]["operator"]["avg_final_capital"] / 1e6 for name in names]
    margin = [results[name]["operator"]["avg_profit_margin_pct"] for name in names]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    series = [
        (bankrupt, "Mira bankrotu", "Bankrot (%)"),
        (capital, "Konecny kapital", "Prumerny kapital (mil. Kc)"),
        (margin, "Ziskova marze", "Marze (%)"),
    ]
    for ax, (values, title, ylabel), color in zip(axes, series, [PALETTE[2], PALETTE[0], PALETTE[1]]):
        bars = ax.bar(names, values, color=color, alpha=0.82)
        top = max(values + [1])
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + top * 0.02, f"{value:.1f}", ha="center", fontsize=8)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", rotation=35)
    fig.suptitle("Porovnani What-If scenaru", fontsize=14, fontweight="bold")
    _save(fig, output_path)


def generate_all(
    stats: SberStatistik,
    scenario_results: Optional[Dict[str, Dict[str, Any]]] = None,
    output_dir: str | Path = "output",
    config: Optional[Config] = None,
) -> None:
    # vygenerovat vsechny grafy najednou
    cfg = config or Config()
    output_dir = Path(output_dir)
    print("\nGeneruji grafy...")

    plot_strategy_roi(stats, output_dir / "strategy_roi.png")
    plot_strategy_cumulative_loss(stats, output_dir / "strategy_cumulative_loss.png")
    plot_strategy_bankruptcy(stats, output_dir / "strategy_bankruptcy.png")
    plot_agent_survival(stats, output_dir / "agent_survival.png")

    plot_operator_capital_distribution(stats, output_dir / "op_capital_distribution.png")
    plot_capital_timeseries(stats, output_dir / "op_capital_timeseries.png")
    plot_operator_cashflow(stats, output_dir / "op_cashflow.png")

    plot_match_probability(stats, cfg, output_dir / "match_probability.png")
    plot_rtp_distribution(stats, cfg, output_dir / "rtp_distribution.png")
    plot_mc_convergence(stats, cfg, output_dir / "mc_convergence_rtp.png")
    plot_number_frequencies(stats, cfg, output_dir / "number_frequencies.png")
    plot_jackpot_expectation(stats, cfg, output_dir / "jackpot_expectation.png")

    if scenario_results:
        plot_scenario_comparison(scenario_results, output_dir / "scenario_comparison.png")

    print(f"\nVsechny grafy ulozeny do '{output_dir}/'")
