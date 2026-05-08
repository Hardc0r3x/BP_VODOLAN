from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, List

from base import Agent
from config import Config
from mc_simulace import MCSimulace
from statistiky import SberStatistik
from tovarna_na_hrace import TovarnaNaHrace


@dataclass
class Scenar:
    name: str
    description: str
    config: Config
    population_builder: Callable[[Config], List[Agent]]


class SpravceScenaru:

    def __init__(self, base_config: Config) -> None:
        self._base = base_config
        self._scenarios = self._build_scenarios()

    @property
    def scenarios(self) -> List[Scenar]:
        return list(self._scenarios)

    def _build_scenarios(self) -> List[Scenar]:
        base = self._base
        return [
            Scenar("baseline", "Standardni mix strategii a typu hracu (referencni stav).", base, TovarnaNaHrace.standard_mix),
            Scenar("aggressive_crowd", "Vsichni hraci jsou agresivni, modeluje vyssi ochotu utracet budget.", base, TovarnaNaHrace.all_aggressive),
            Scenar("all_martingale", "Vsichni hraci pouzivaji Martingale, testuje progresivni navysovani sazek.", base, TovarnaNaHrace.all_martingale),
            Scenar("high_jackpot", "Garantovany jackpot zvysen z 1 mil. na 10 mil. Kc.", replace(base, min_jackpot=10_000_000.0), TovarnaNaHrace.standard_mix),
            Scenar("higher_jackpot_allocation", "Vyssi alokace trzeb do jackpotoveho poolu: 50 % -> 70 %.", replace(base, prize_pool_ratio=0.70), TovarnaNaHrace.standard_mix),
            Scenar("low_operator_capital", "Nizsi pocatecni kapital provozovatele: 10 mil. -> 2 mil. Kc.", replace(base, operator_initial_capital=2_000_000.0), TovarnaNaHrace.standard_mix),
            Scenar("small_population", "Pouze 20 hracu misto 100, nizsi diverzifikace a mensi trh.", replace(base, num_agents=20), TovarnaNaHrace.standard_mix),
        ]

    def get(self, scenario_name: str) -> Scenar | None:
        for scenario in self._scenarios:
            if scenario.name == scenario_name:
                return scenario
        return None

    def add_scenario(self, scenario: Scenar) -> None:
        self._scenarios.append(scenario)

    def run_all(self, verbose: bool = True) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        for scenario in self._scenarios:
            if verbose:
                print(f"\n  Scenar: {scenario.name}")
                print(f"  {scenario.description}")
                print(f"  Spoustim {scenario.config.num_simulations} behu...")

            agents = scenario.population_builder(scenario.config)
            stats = SberStatistik()
            MCSimulace(scenario.config, agents, stats).run()

            results[scenario.name] = {
                "operator": stats.get_operator_stats(),
                "strategies": stats.get_strategy_stats(),
                "config": scenario.config,
                "description": scenario.description,
                "collector": stats,
            }

            if verbose:
                op = results[scenario.name]["operator"]
                print(
                    f"  Hotovo - bankrot: {op['bankruptcy_rate_pct']:.1f} % | "
                    f"kapital: {op['avg_final_capital']:>12,.0f} Kc | "
                    f"marze: {op['avg_profit_margin_pct']:.1f} %"
                )
        return results

    def print_comparison(self, results: Dict[str, Dict[str, Any]]) -> None:
        print("\n" + "=" * 96)
        print(f"{'POROVNANI WHAT-IF SCENARU':^96}")
        print("=" * 96)
        print(f"{'SCENAR':<28} {'BANKROT':>9} {'KAPITAL AVG':>16} {'MARZE':>9} {'RTP TEOR.':>10}")
        print("-" * 96)
        for name, data in results.items():
            op = data["operator"]
            cfg: Config = data["config"]
            print(
                f"{name:<28} "
                f"{op['bankruptcy_rate_pct']:>8.1f}% "
                f"{op['avg_final_capital']:>15,.0f} Kc "
                f"{op['avg_profit_margin_pct']:>8.1f}% "
                f"{cfg.theoretical_rtp():>9.1f}%"
            )
        print("=" * 96)

    def export_comparison_csv(self, results: Dict[str, Dict[str, Any]], output_path: str | Path) -> None:
        rows = []
        for name, data in results.items():
            op = data["operator"]
            cfg: Config = data["config"]
            rows.append({
                "scenario": name, "description": data["description"],
                "num_agents": cfg.num_agents, "num_rounds": cfg.num_rounds,
                "num_simulations": cfg.num_simulations, "min_jackpot": cfg.min_jackpot,
                "operator_initial_capital": cfg.operator_initial_capital,
                "prize_pool_ratio": cfg.prize_pool_ratio,
                "theoretical_rtp_pct": cfg.theoretical_rtp(),
                "bankruptcy_rate_pct": op["bankruptcy_rate_pct"],
                "avg_final_capital": op["avg_final_capital"],
                "avg_profit_margin_pct": op["avg_profit_margin_pct"],
                "avg_total_revenue": op["avg_total_revenue"],
                "avg_total_payouts": op["avg_total_payouts"],
            })
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
