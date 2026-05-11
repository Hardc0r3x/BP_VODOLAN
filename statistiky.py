from __future__ import annotations

# Soubor sbira a zpracovava vysledky simulace.
# Z techto dat se pak delaji tabulky, grafy a CSV vystupy.

import csv
from dataclasses import dataclass
from math import comb
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from scipy import stats as scipy_stats


# struktura pro ulozeni vysledku jednoho MC behu
@dataclass
class VysledekBehu:
    # cislo MC behu
    run_id: int
    # souhrn provozovatele za jeden beh
    operator_summary: Dict[str, Any]
    # souhrny vsech agentu v behu
    agent_summaries: List[Dict[str, Any]]
    # souhrny jednotlivych kol
    round_data: List[Dict[str, Any]]


# sberac statistik - sbira data ze vsech MC behu a pak je umi zpracovat
class SberStatistik:

    def __init__(self) -> None:
        # sem se ukladaji vysledky vsech MC behu
        self._runs: List[VysledekBehu] = []
        # pocitadla vyher podle poctu shod
        self._prize_counts: Dict[int, int] = {3: 0, 4: 0, 5: 0, 6: 0}
        self._total_tickets: int = 0
        self._prize_counts_by_strategy: Dict[str, Dict[int, int]] = {}
        self._ticket_counts_by_strategy: Dict[str, int] = {}
        self._jackpot_events: List[Dict[str, Any]] = []

    def record_run(
        self,
        run_id: int,
        operator_summary: Dict[str, Any],
        agent_summaries: List[Dict[str, Any]],
        round_data: List[Dict[str, Any]],
    ) -> None:
        # ulozime zkracene zaznamy agentu, aby se setrila pamet
        stored_agents: List[Dict[str, Any]] = []

        # projdeme vsechny agenty z jednoho behu
        for agent in agent_summaries:
            # zjistime strategii agenta
            strategy = agent.get("strategy", "Unknown")
            self._prize_counts_by_strategy.setdefault(strategy, {3: 0, 4: 0, 5: 0, 6: 0})
            self._ticket_counts_by_strategy.setdefault(strategy, 0)

            # historie agenta se zkrati jen na dulezite polozky
            slim_history = []
            for result in agent.get("history", []):
                # pocet tiketu v danem kole
                n_tickets = int(result.get("tickets", 0) or 0)
                ticket_matches = result.get("ticket_matches")

                # pokud mame shody po jednotlivych tiketech, pocitame kazdy tiket zvlast
                if isinstance(ticket_matches, list):
                    for matches in ticket_matches:
                        matches = int(matches)
                        if matches >= 3:
                            self._prize_counts[matches] += 1
                            self._prize_counts_by_strategy[strategy][matches] += 1
                else:
                    matches = int(result.get("matches", 0) or 0)
                    if matches >= 3:
                        self._prize_counts[matches] += 1
                        self._prize_counts_by_strategy[strategy][matches] += 1

                # pricteme tikety do globalniho i strategickeho souctu
                self._total_tickets += n_tickets
                self._ticket_counts_by_strategy[strategy] += n_tickets

                # ukladam jen to co potrebuju, plna historie by zabirala moc pameti
                slim_history.append({
                    "round": result.get("round"),
                    "tickets": n_tickets,
                    "cost": float(result.get("cost", 0) or 0),
                    "prize": float(result.get("prize", 0) or 0),
                    "matches": int(result.get("matches", 0) or 0),
                    "budget": float(result.get("budget", 0) or 0),
                    "unpaid_prize": float(result.get("unpaid_prize", 0) or 0),
                })

            # vytvorime kopii agenta se zkracenou historii
            stored_agent = dict(agent)
            stored_agent["history"] = slim_history
            stored_agents.append(stored_agent)

        # jackpotove udalosti ukladame zvlast pro diagnostiku
        for round_row in round_data:
            for event in round_row.get("jackpot_events", []) or []:
                self._jackpot_events.append(dict(event))

        # do beznych kol uz jackpot_events nedavame, aby se data neduplikovala
        stored_rounds = []
        for row in round_data:
            slim_row = dict(row)
            slim_row.pop("jackpot_events", None)
            stored_rounds.append(slim_row)

        # nakonec ulozime jeden hotovy MC beh
        self._runs.append(VysledekBehu(run_id, operator_summary, stored_agents, stored_rounds))

    @property
    def num_runs(self) -> int:
        return len(self._runs)

    @property
    def runs(self) -> List[VysledekBehu]:
        return self._runs

    def total_tickets(self) -> int:
        return self._total_tickets

    def clear(self) -> None:
        self._runs.clear()
        self._prize_counts = {3: 0, 4: 0, 5: 0, 6: 0}
        self._total_tickets = 0
        self._prize_counts_by_strategy.clear()
        self._ticket_counts_by_strategy.clear()
        self._jackpot_events.clear()

    def get_operator_stats(self) -> Dict[str, Any]:
        # souhrnne statistiky provozovatele pres vsechny behy
        if not self._runs:
            return {}

        # vybereme zakladni rady hodnot z ulozenych behu
        finals = np.array([r.operator_summary["final_capital"] for r in self._runs], dtype=float)
        profits = np.array([r.operator_summary["net_profit"] for r in self._runs], dtype=float)
        margins = np.array([r.operator_summary["profit_margin"] for r in self._runs], dtype=float)
        bankrupt = np.array([r.operator_summary["bankrupt"] for r in self._runs], dtype=float)
        revenues = np.array([r.operator_summary.get("total_revenue", 0) for r in self._runs], dtype=float)
        payouts = np.array([r.operator_summary.get("total_payouts", 0) for r in self._runs], dtype=float)

        # prumer z boolean hodnot dava podil bankrotu
        bankruptcy_rate = float(np.mean(bankrupt) * 100)
        total_revenue_all = float(np.sum(revenues))
        total_payouts_all = float(np.sum(payouts))
        # vratime slovnik hodnot pro tabulky a grafy
        return {
            "num_runs": len(self._runs),
            "bankruptcy_rate_pct": bankruptcy_rate,
            "avg_final_capital": float(np.mean(finals)),
            "std_final_capital": float(np.std(finals)),
            "min_final_capital": float(np.min(finals)),
            "max_final_capital": float(np.max(finals)),
            "pct1_final_capital": float(np.percentile(finals, 1)),
            "pct5_final_capital": float(np.percentile(finals, 5)),
            "pct95_final_capital": float(np.percentile(finals, 95)),
            "avg_net_profit": float(np.mean(profits)),
            "avg_profit_margin_pct": float(np.mean(margins)),
            "risk_adjusted_profit": float(np.mean(profits) * (1 - bankruptcy_rate / 100)),
            "avg_total_revenue": float(np.mean(revenues)),
            "avg_total_payouts": float(np.mean(payouts)),
            "avg_empirical_rtp_pct": float(np.mean(np.divide(payouts, revenues, out=np.zeros_like(payouts), where=revenues > 0) * 100)),
            "global_empirical_rtp_pct": total_payouts_all / total_revenue_all * 100 if total_revenue_all else 0.0,
            "global_profit_margin_pct": (1 - total_payouts_all / total_revenue_all) * 100 if total_revenue_all else 0.0,
            "total_unpaid_liabilities": float(sum(r.operator_summary.get("unpaid_liabilities", 0.0) for r in self._runs)),
            "max_unpaid_prize": float(max((r.operator_summary.get("largest_unpaid_prize", 0.0) for r in self._runs), default=0.0)),
        }

    def calculate_theoretical_odds(self, num_balls: int = 49, draw_size: int = 6) -> Dict[int, float]:
        # teoreticke pravdepodobnosti z kombinatoriky
        # celkovy pocet moznych tiketu
        total_combinations = comb(num_balls, draw_size)
        odds = {}
        for matches in [3, 4, 5, 6]:
            if matches > draw_size or draw_size - matches > num_balls - draw_size:
                odds[matches] = 0.0
                continue
            # pocet kombinaci, ktere trefi presne dany pocet cisel
            ways = comb(draw_size, matches) * comb(num_balls - draw_size, draw_size - matches)
            odds[matches] = ways / total_combinations * 100
        return odds

    def get_prize_stats(self, config=None) -> Dict[int, Dict[str, Any]]:
        # porovnani empirickych a teoretickych pravdepodobnosti vyher
        theoretical_odds = {}
        if config is not None:
            theoretical_odds = self.calculate_theoretical_odds(config.num_balls, config.draw_size)

        results: Dict[int, Dict[str, Any]] = {}
        for matches in [3, 4, 5, 6]:
            count = self._prize_counts.get(matches, 0)
            pct_actual = count / self._total_tickets * 100 if self._total_tickets else 0.0
            results[matches] = {
                "count": count,
                "pct_actual": pct_actual,
                "pct_theoretical": theoretical_odds.get(matches, 0.0),
            }
        return results

    def get_strategy_stats(self) -> Dict[str, Dict[str, Any]]:
        # souhrnne metriky pro kazdou strategii pres vsechny behy
        # agenty si rozdelime podle strategie
        strategy_data: Dict[str, List[Dict[str, Any]]] = {}
        for run in self._runs:
            for agent in run.agent_summaries:
                strategy_data.setdefault(agent["strategy"], []).append(agent)

        results: Dict[str, Dict[str, Any]] = {}
        # pro kazdou strategii spocitame vlastni metriky
        for strategy, agents in strategy_data.items():
            # z agentu vytahneme zakladni ekonomicke vysledky
            rois = np.array([a["roi"] for a in agents], dtype=float)
            profits = np.array([a["net_profit"] for a in agents], dtype=float)
            inactive = np.array([not a["active"] for a in agents], dtype=float)
            bankr = np.array([a.get("actual_bankrupt", False) for a in agents], dtype=float)
            skipped = np.array([a.get("skipped_rounds", 0) for a in agents], dtype=float)
            total_spent = float(sum(a.get("total_spent", 0) for a in agents))
            total_won = float(sum(a.get("total_won", 0) for a in agents))
            strategy_tickets = int(self._ticket_counts_by_strategy.get(strategy, 0))
            strategy_wins = int(sum(self._prize_counts_by_strategy.get(strategy, {}).get(m, 0) for m in [3, 4, 5, 6]))

            # ulozime souhrn jedne strategie
            results[strategy] = {
                "count": len(agents),
                "avg_roi_pct": float(np.mean(rois)),
                "std_roi_pct": float(np.std(rois)),
                "median_roi_pct": float(np.median(rois)),
                "pct5_roi": float(np.percentile(rois, 5)),
                "pct95_roi": float(np.percentile(rois, 95)),
                "avg_net_profit": float(np.mean(profits)),
                "std_net_profit": float(np.std(profits)),
                "bankruptcy_rate_pct": float(np.mean(bankr) * 100),
                "inactive_rate_pct": float(np.mean(inactive) * 100),
                "avg_skipped_rounds": float(np.mean(skipped)),
                "total_tickets": strategy_tickets,
                "total_wins": strategy_wins,
                "avg_prize_per_ticket": total_won / strategy_tickets if strategy_tickets else 0.0,
                "tickets_per_win": strategy_tickets / strategy_wins if strategy_wins else float("inf"),
                "win_rate_pct": strategy_wins / strategy_tickets * 100 if strategy_tickets else 0.0,
                "total_spent": total_spent,
                "total_won": total_won,
                "yield_pct": (total_won - total_spent) / total_spent * 100 if total_spent else 0.0,
            }
        return results

    def get_strategy_tests(self) -> Dict[str, Any]:
        # statisticke testy jestli se strategie od sebe vyznacne lisi
        # skupiny ROI podle strategie, agregovane po MC bezich
        groups: Dict[str, List[float]] = {}
        for run in self._runs:
            by_strategy: Dict[str, List[float]] = {}
            for agent in run.agent_summaries:
                by_strategy.setdefault(agent["strategy"], []).append(float(agent["roi"]))
            for strategy, values in by_strategy.items():
                if values:
                    groups.setdefault(strategy, []).append(float(np.mean(values)))

        # testujeme jen strategie, ktere maji aspon dva behy
        arrays_by_name = {k: np.array(v, dtype=float) for k, v in groups.items() if len(v) >= 2}
        if len(arrays_by_name) < 2:
            return {"global": {}, "shapiro": [], "pairwise": []}

        # kruskal-wallis test - neparametricky test pro vic skupin
        kw = scipy_stats.kruskal(*arrays_by_name.values())

        # shapiro-wilk test normality pro kazdou strategii zvlast
        shapiro_rows = []
        for name, values in arrays_by_name.items():
            sample = values[:5000]
            if len(sample) < 3 or float(np.max(sample) - np.min(sample)) == 0.0:
                shapiro_rows.append({
                    "strategy": name,
                    "n": len(values),
                    "sample_n": len(sample),
                    "statistic": float("nan"),
                    "p_value": float("nan"),
                })
                continue
            sh = scipy_stats.shapiro(sample)
            shapiro_rows.append({
                "strategy": name,
                "n": len(values),
                "sample_n": len(sample),
                "statistic": float(sh.statistic),
                "p_value": float(sh.pvalue),
            })

        # parove mann-whitney testy s bonferroniho korekci
        # pripravime dvojice strategii pro parove testy
        names = sorted(arrays_by_name)
        raw_pairs = []
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                test = scipy_stats.mannwhitneyu(arrays_by_name[a], arrays_by_name[b], alternative="two-sided")
                raw_pairs.append({
                    "strategy_a": a,
                    "strategy_b": b,
                    "u_statistic": float(test.statistic),
                    "p_value_raw": float(test.pvalue),
                })
        m = max(len(raw_pairs), 1)
        pairwise = []
        for row in raw_pairs:
            corrected = min(row["p_value_raw"] * m, 1.0)
            pairwise.append({**row, "p_value_bonferroni": corrected})

        return {
            "global": {
                "test": "Kruskal-Wallis",
                "unit": "run_level_strategy_mean_roi",
                "h_statistic": float(kw.statistic),
                "p_value": float(kw.pvalue),
                "groups": len(arrays_by_name),
            },
            "shapiro": shapiro_rows,
            "pairwise": pairwise,
        }

    def get_convergence_stats(self) -> Dict[str, Any]:
        # prubezny prumer RTP pres behy - ukazuje konvergenci monte carlo
        rtps = []
        running = []
        for run in self._runs:
            rev = float(run.operator_summary.get("total_revenue", 0) or 0)
            pay = float(run.operator_summary.get("total_payouts", 0) or 0)
            if rev > 0:
                rtps.append(pay / rev * 100)
                running.append(float(np.mean(rtps)))
        return {
            "rtp_by_run": rtps,
            "running_mean_rtp": running,
            "final_mean_rtp": running[-1] if running else 0.0,
        }

    def get_jackpot_diagnostics(self, config) -> Dict[str, Any]:
        # zakladni diagnostiku jackpotu vezmeme z konfigurace
        diag = config.jackpot_diagnostics(self._total_tickets)
        jackpot_count = self._prize_counts.get(config.draw_size, 0)
        diag["observed_jackpots"] = jackpot_count
        diag["observed_jackpot_rate"] = jackpot_count / self._total_tickets if self._total_tickets else 0.0
        diag["jackpot_events_recorded"] = len(self._jackpot_events)
        return diag

    def export_csv(self, output_dir: str | Path, config=None) -> None:
        # export vsech vysledku do CSV souboru
        # pripravime vystupni slozku pro CSV soubory
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # souhrn po jednotlivych MC bezich
        run_rows = []
        for run in self._runs:
            rev = float(run.operator_summary.get("total_revenue", 0) or 0)
            pay = float(run.operator_summary.get("total_payouts", 0) or 0)
            run_rows.append({
                "run_id": run.run_id,
                "rounds": len(run.round_data),
                "total_revenue": rev,
                "total_payouts": pay,
                "rtp_pct": pay / rev * 100 if rev else 0.0,
                "final_capital": run.operator_summary.get("final_capital", 0.0),
                "net_profit": run.operator_summary.get("net_profit", 0.0),
                "profit_margin_pct": run.operator_summary.get("profit_margin", 0.0),
                "bankrupt": run.operator_summary.get("bankrupt", False),
            })
        _write_csv(out / "run_summary.csv", run_rows)

        # souhrn podle strategii
        strategy_rows = [{"strategy": name, **row} for name, row in self.get_strategy_stats().items()]
        _write_csv(out / "strategy_summary.csv", strategy_rows)

        # souhrn strategie v kazdem konkretnim behu
        run_strategy_rows = []
        for run in self._runs:
            by_strategy: Dict[str, List[Dict[str, Any]]] = {}
            for agent in run.agent_summaries:
                by_strategy.setdefault(agent["strategy"], []).append(agent)
            for strategy, agents in by_strategy.items():
                spent = float(sum(a.get("total_spent", 0) for a in agents))
                won = float(sum(a.get("total_won", 0) for a in agents))
                run_strategy_rows.append({
                    "run_id": run.run_id,
                    "strategy": strategy,
                    "agent_count": len(agents),
                    "avg_roi_pct": float(np.mean([a.get("roi", 0) for a in agents])),
                    "yield_pct": (won - spent) / spent * 100 if spent else 0.0,
                    "bankruptcy_rate_pct": float(np.mean([a.get("actual_bankrupt", False) for a in agents]) * 100),
                    "inactive_rate_pct": float(np.mean([not a.get("active", True) for a in agents]) * 100),
                    "total_spent": spent,
                    "total_won": won,
                })
        _write_csv(out / "run_strategy_summary.csv", run_strategy_rows)
        _write_csv(out / "jackpot_events.csv", self._jackpot_events)

        if config is not None:
            # tabulka porovnani empirickych a teoretickych vyher
            prize_rows = [{"match_count": k, **row} for k, row in self.get_prize_stats(config).items()]
            _write_csv(out / "prize_summary.csv", prize_rows)

            jackpot = self.get_jackpot_diagnostics(config)
            _write_csv(out / "jackpot_diagnostics.csv", [jackpot])

        tests = self.get_strategy_tests()
        if tests["global"]:
            _write_csv(out / "strategy_global_tests.csv", [tests["global"]])
            _write_csv(out / "strategy_shapiro_tests.csv", tests["shapiro"])
            _write_csv(out / "strategy_pairwise_tests.csv", tests["pairwise"])

    def print_summary(self, config=None) -> None:
        # pripravime hlavni souhrny pro vypis do konzole
        op = self.get_operator_stats()
        strats = self.get_strategy_stats()
        prizes = self.get_prize_stats(config)

        print("=" * 60)
        print("VYSLEDKY SIMULACE - PROVOZOVATEL")
        print("=" * 60)
        print(f"  Pocet behu: {op['num_runs']}")
        print(f"  Mira bankrotu: {op['bankruptcy_rate_pct']:.2f} %")
        print(f"  Prumerny koncovy kapital: {op['avg_final_capital']:>14,.0f} CZK")
        print(f"  5. percentil kapitalu: {op['pct5_final_capital']:>14,.0f} CZK")
        print(f"  95. percentil kapitalu: {op['pct95_final_capital']:>14,.0f} CZK")
        print(f"  Prumerna marze: {op['avg_profit_margin_pct']:>14.2f} %")
        print(f"  Globalni marze: {op['global_profit_margin_pct']:>14.2f} %")
        print(f"  Prumerne empiricke RTP: {op['avg_empirical_rtp_pct']:>14.2f} %")
        print(f"  Globalni empiricke RTP: {op['global_empirical_rtp_pct']:>14.2f} %")

        print("\n" + "=" * 60)
        print("VYSLEDKY SIMULACE - VYHRY")
        print("=" * 60)
        print(f"  Celkem tiketu: {self._total_tickets:>14,}")
        for matches in [3, 4, 5, 6]:
            p = prizes[matches]
            label = {3: "3 shody", 4: "4 shody", 5: "5 shod", 6: "JACKPOT"}[matches]
            print(f"  {label:10}: {p['count']:>10,} | empiricky {p['pct_actual']:.6f} % | teorie {p['pct_theoretical']:.6f} %")

        print("\n" + "=" * 60)
        print("VYSLEDKY SIMULACE - STRATEGIE")
        print("=" * 60)
        for name, s in sorted(strats.items()):
            print(f"\n  Strategie: {name}")
            print(f"    Prumerne ROI: {s['avg_roi_pct']:>10.2f} %")
            print(f"    Median ROI: {s['median_roi_pct']:>10.2f} %")
            print(f"    Std ROI: {s['std_roi_pct']:>10.2f} %")
            print(f"    YIELD: {s['yield_pct']:>10.2f} %")
            print(f"    Mira bankrotu: {s['bankruptcy_rate_pct']:>10.2f} %")
            print(f"    Neaktivni hraci: {s['inactive_rate_pct']:>10.2f} %")
            print(f"    Celkem tiketu: {s['total_tickets']:>10,}")
            print(f"    Vyherni tikety: {s['total_wins']:>10,}")
        print("=" * 60)


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    # kdyz nejsou radky, vytvorime prazdny soubor
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # zapiseme CSV s hlavickou
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
