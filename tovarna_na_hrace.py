from __future__ import annotations

# Soubor vytvari populaci hracu.
# Drzi pomer strategii a typu hracu pro jednotlive scenare.
import random
from typing import Callable, List

from config import Config
from base import Agent, Strategy
from opatrny_hrac import OpatrnyHrac
from agresivni_hrac import AgresivniHrac
from nahodna_strategie import NahodnaStrategie
from fixed_cisla import FixedCisla
from martingale_strategie import MartingaleStrategie
from hot_cold_strategie import HotColdStrategie


# tovarna na hrace - centralni misto pro vytvoreni populace
class TovarnaNaHrace:

    @classmethod
    def standard_mix(cls, config: Config) -> List[Agent]:
        # standardni mix pouzity v hlavnim experimentu
        strategies: List[tuple[str, Callable[[], Strategy]]] = [
            ("Nahodna", lambda: NahodnaStrategie()),
            ("FixedCisla", lambda: FixedCisla()),
            ("Martingale", lambda: MartingaleStrategie(base_tickets=1, max_tickets=config.martingale_max_tickets)),
            ("HotCold_hot", lambda: HotColdStrategie(mode="hot", candidate_pool_multiplier=config.hot_cold_pool_multiplier)),
            ("HotCold_cold", lambda: HotColdStrategie(mode="cold", candidate_pool_multiplier=config.hot_cold_pool_multiplier)),
        ]
        # vratime vyvazenou populaci s opatrnymi i agresivnimi hraci
        return cls._build_balanced(config, strategies, aggressive_only=False)

    @classmethod
    def all_aggressive(cls, config: Config) -> List[Agent]:
        # stejny mix strategii, ale vsichni hraci jsou agresivni
        strategies: List[tuple[str, Callable[[], Strategy]]] = [
            ("Nahodna", lambda: NahodnaStrategie()),
            ("FixedCisla", lambda: FixedCisla()),
            ("Martingale", lambda: MartingaleStrategie(base_tickets=1, max_tickets=config.martingale_max_tickets)),
            ("HotCold_hot", lambda: HotColdStrategie(mode="hot", candidate_pool_multiplier=config.hot_cold_pool_multiplier)),
            ("HotCold_cold", lambda: HotColdStrategie(mode="cold", candidate_pool_multiplier=config.hot_cold_pool_multiplier)),
        ]
        # aggressive_only znamena, ze se nevytvareji opatrni hraci
        return cls._build_balanced(config, strategies, aggressive_only=True)

    @classmethod
    def all_martingale(cls, config: Config) -> List[Agent]:
        # scenar, kde vsichni pouzivaji jen Martingale
        strategies = [("Martingale", lambda: MartingaleStrategie(base_tickets=1, max_tickets=config.martingale_max_tickets))]
        return cls._build_balanced(config, strategies, aggressive_only=False)

    @classmethod
    def _build_balanced(
        cls,
        config: Config,
        strategies: List[tuple[str, Callable[[], Strategy]]],
        aggressive_only: bool = False,
    ) -> List[Agent]:
        # vlastni random pro rozpocet agentu, aby byl mix opakovatelny
        rng = random.Random(config.seed)
        n_total = config.num_agents
        n_strategies = len(strategies)

        # spocitame kolik agentu pripadne na jednu strategii
        base_count = n_total // n_strategies
        remainder = n_total % n_strategies
        counts = [base_count + (1 if i < remainder else 0) for i in range(n_strategies)]
        max_count = max(counts) if counts else 0

        # stejne poradi rozpocetu pro kazdou strategii, aby byly strategie feroveji porovnane
        paired_budgets = [rng.uniform(*config.agent_budget_range) for _ in range(max_count)]
        agents: List[Agent] = []
        agent_idx = 0

        # projdeme jednotlive strategie a vytvorime pro ne hrace
        for strategy_idx, (_, strategy_factory) in enumerate(strategies):
            count = counts[strategy_idx]
            # pomer opatrnych se pocita uvnitr kazde strategicke skupiny
            # v kazde strategii urcime kolik hracu bude opatrnych
            cautious_count = 0 if aggressive_only else round(count * config.agent_cautious_ratio)
            for i in range(count):
                # hrac dostane rozpocet z predem pripravenych hodnot
                budget = paired_budgets[i]
                # pro kazdeho agenta vytvorime novou instanci strategie
                strategy = strategy_factory()
                agent_id = f"agent_{agent_idx:03d}"
                is_cautious = (i < cautious_count) and not aggressive_only
                # podle typu vytvorime opatrneho nebo agresivniho hrace
                if is_cautious:
                    agent: Agent = OpatrnyHrac(
                        agent_id=agent_id,
                        initial_budget=budget,
                        strategy=strategy,
                        ticket_price=config.ticket_price,
                        safety_threshold=0.20,
                        min_reserve=100.0,
                    )
                else:
                    agent = AgresivniHrac(
                        agent_id=agent_id,
                        initial_budget=budget,
                        strategy=strategy,
                        ticket_price=config.ticket_price,
                    )
                agents.append(agent)
                agent_idx += 1
        return agents[:n_total]
