from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from config import Config
from mc_simulace import MCSimulace
from real_lottery_reference import export_reference_outputs
from scenare import SpravceScenaru
from statistiky import SberStatistik
from tovarna_na_hrace import TovarnaNaHrace
from vizualizace import generate_all, plot_scenario_comparison


# dostupne profily pro spusteni
PROFILES = {
    "quick": "rychla kontrola (100 MC behu)",
    "thesis": "hlavni experiment pro BP (1 000 MC behu)",
    "deep": "velky beh pro overeni stability (10 000 MC behu, bez scenaru)",
}


def _print_header(profile: str, config: Config, agents: list | None = None) -> None:
    print("=" * 72)
    print("  Simulace hernich strategii v ciselnych loteriich")
    print("  Bakalarska prace - agentni modelovani a Monte Carlo")
    print("=" * 72)
    print(f"Profil: {profile} - {PROFILES[profile]}")
    print("\nKonfigurace:")
    print(config.summary_str(agents))


def _print_population(agents) -> None:
    # vypise kolik agentu hraje jakou strategii
    counts: dict[str, int] = {}
    for agent in agents:
        counts[agent.strategy.name] = counts.get(agent.strategy.name, 0) + 1
    print(f"\nPopulace ({len(agents)} agentu):")
    for strategy, count in sorted(counts.items()):
        print(f"  {strategy:<25} {count:>4} agentu")


def run_baseline(config: Config, output_dir: Path, profile: str) -> SberStatistik:
    # zakladni simulace se standardnim mixem strategii
    agents = TovarnaNaHrace.standard_mix(config)
    _print_header(profile, config, agents)
    _print_population(agents)

    print(f"\nSpoustim zakladni simulaci ({config.num_simulations} behu)...")
    stats = SberStatistik()
    sim = MCSimulace(config=config, agents=agents, stats_collector=stats)

    # progress bar aby bylo videt jak daleko to je
    pbar = tqdm(total=config.num_simulations, unit="beh")
    sim.set_progress_callback(lambda done, total: pbar.update(1))
    sim.run()
    pbar.close()

    stats.print_summary(config=config)

    # vygenerovat grafy a exportovat data
    figures_dir = output_dir / "figures"
    csv_dir = output_dir / "csv"
    generate_all(stats, scenario_results=None, output_dir=str(figures_dir), config=config)
    stats.export_csv(csv_dir, config=config)
    export_reference_outputs(output_dir / "reference")

    # ulozit metadata o behu aby bylo jasne s cim se to pustilo
    metadata = {
        "profile": profile,
        "config": asdict(config),
        "theoretical_rtp_pct": config.theoretical_rtp(),
        "expected_value_per_ticket": config.expected_value_per_ticket(),
        "note": "Zjednoduseny model 6/49. Neslouzi jako presna kalibrace komercni loterie.",
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def run_scenarios(base_config: Config, output_dir: Path) -> dict:
    # pustit vsechny what-if scenare
    print("\n" + "=" * 72)
    print("  What-If scenare")
    print("=" * 72)
    runner = SpravceScenaru(base_config)
    results = runner.run_all(verbose=True)
    runner.print_comparison(results)
    runner.export_comparison_csv(results, output_dir / "csv" / "scenario_summary.csv")
    plot_scenario_comparison(results, str(output_dir / "figures" / "scenario_comparison.png"))
    return results


def run_specific_scenario(scenario_name: str, base_config: Config, output_dir: Path, profile: str) -> None:
    # spustit jeden konkretni scenar
    runner = SpravceScenaru(base_config)
    scenario = runner.get(scenario_name)
    if scenario is None:
        print(f"Neznamy scenar: {scenario_name}")
        print("\nDostupne scenare:")
        for item in runner.scenarios:
            print(f"  {item.name:<28} {item.description}")
        return

    config = scenario.config
    agents = scenario.population_builder(config)
    _print_header(profile, config, agents)
    print(f"\nScenar: {scenario.name}")
    print(scenario.description)
    _print_population(agents)

    print(f"\nSpoustim scenar ({config.num_simulations} behu)...")
    stats = SberStatistik()
    sim = MCSimulace(config=config, agents=agents, stats_collector=stats)
    pbar = tqdm(total=config.num_simulations, unit="beh")
    sim.set_progress_callback(lambda done, total: pbar.update(1))
    sim.run()
    pbar.close()

    stats.print_summary(config=config)
    scenario_out = output_dir / scenario.name
    generate_all(stats, scenario_results=None, output_dir=str(scenario_out / "figures"), config=config)
    stats.export_csv(scenario_out / "csv", config=config)
    print(f"\nVystupy scenare jsou ve slozce: {scenario_out}")


def list_scenarios(base_config: Config) -> None:
    runner = SpravceScenaru(base_config)
    print("\nDostupne scenare:")
    for scenario in runner.scenarios:
        print(f"  {scenario.name:<28} {scenario.description}")


def build_config_from_args(args: argparse.Namespace) -> Config:
    # vezme profil a pripadne prepsane hodnoty z prikazove radky
    config = Config.profile(args.profile)
    overrides = {}
    if args.simulations is not None:
        overrides["num_simulations"] = args.simulations
    if args.rounds is not None:
        overrides["num_rounds"] = args.rounds
    if args.agents is not None:
        overrides["num_agents"] = args.agents
    if args.seed is not None:
        overrides["seed"] = args.seed
    if overrides:
        config = replace(config, **overrides)
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulace hernich strategii v ciselnych loteriich",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Priklady:
  uv run main.py
  uv run main.py --profile quick
  uv run main.py --profile thesis --scenarios
  uv run main.py --profile deep
  uv run main.py --scenario all_martingale
  uv run main.py --list-scenarios
        """,
    )
    parser.add_argument("--profile", choices=PROFILES.keys(), default="thesis")
    parser.add_argument("--scenarios", action="store_true", help="Spustit vsechny What-If scenare po baseline")
    parser.add_argument("--scenario", type=str, default=None, help="Spustit pouze konkretni scenar")
    parser.add_argument("--list-scenarios", action="store_true", help="Vypsat dostupne scenare")
    parser.add_argument("--simulations", type=int, default=None, help="Prepsat pocet MC behu")
    parser.add_argument("--rounds", type=int, default=None, help="Prepsat pocet kol na jeden beh")
    parser.add_argument("--agents", type=int, default=None, help="Prepsat pocet agentu")
    parser.add_argument("--seed", type=int, default=None, help="Prepsat seed")
    parser.add_argument("--output-dir", type=str, default=None, help="Vystupni slozka")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = build_config_from_args(args)
    output_dir = Path(args.output_dir or f"output_{args.profile}")
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.list_scenarios:
        list_scenarios(config)
        return

    if args.scenario:
        run_specific_scenario(args.scenario, config, output_dir, args.profile)
        return

    # hlavni beh - zakladni simulace
    run_baseline(config, output_dir, args.profile)

    # volitelne scenare po baseline
    if args.scenarios:
        if args.profile == "deep":
            print("\nProfil deep je urceny pro baseline. Scenare spust pres --profile thesis nebo quick.")
        else:
            run_scenarios(config, output_dir)

    print("\nSimulace dokoncena.")
    print(f"Vystupy jsou ve slozce: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
