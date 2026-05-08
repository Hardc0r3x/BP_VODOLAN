from __future__ import annotations
import random
from typing import Callable, List, Tuple

from config import Config
from base import Agent, Strategy
from opatrny_hrac import OpatrnyHrac
from agresivni_hrac import AgresivniHrac
from nahodna_strategie import NahodnaStrategie
from fixed_cisla import FixedCisla
from martingale_strategie import MartingaleStrategie
from hot_cold_strategie import HotColdStrategie


TypPopulace = List[Tuple[float, type, str]]


class TovarnaNaHrace:

    @classmethod
    def standard_mix(cls, config: Config) -> List[Agent]:
        strategies: List[tuple[str, Callable[[], Strategy]]] = [
            ("Nahodna", lambda: NahodnaStrategie()),
            ("FixedCisla", lambda: FixedCisla()),
            ("Martingale", lambda: MartingaleStrategie(base_tickets=1, max_tickets=config.martingale_max_tickets)),
            ("HotCold_hot", lambda: HotColdStrategie(mode="hot", candidate_pool_multiplier=config.hot_cold_pool_multiplier)),
            ("HotCold_cold", lambda: HotColdStrategie(mode="cold", candidate_pool_multiplier=config.hot_cold_pool_multiplier)),
        ]
        return cls._build_balanced(config, strategies, aggressive_only=False)

    @classmethod
    def all_aggressive(cls, config: Config) -> List[Agent]:
        strategies: List[tuple[str, Callable[[], Strategy]]] = [
            ("Nahodna", lambda: NahodnaStrategie()),
            ("FixedCisla", lambda: FixedCisla()),
            ("Martingale", lambda: MartingaleStrategie(base_tickets=1, max_tickets=config.martingale_max_tickets)),
            ("HotCold_hot", lambda: HotColdStrategie(mode="hot", candidate_pool_multiplier=config.hot_cold_pool_multiplier)),
            ("HotCold_cold", lambda: HotColdStrategie(mode="cold", candidate_pool_multiplier=config.hot_cold_pool_multiplier)),
        ]
        return cls._build_balanced(config, strategies, aggressive_only=True)

    @classmethod
    def all_martingale(cls, config: Config) -> List[Agent]:
        strategies = [("Martingale", lambda: MartingaleStrategie(base_tickets=1, max_tickets=config.martingale_max_tickets))]
        return cls._build_balanced(config, strategies, aggressive_only=False)

    @classmethod
    def custom(cls, config: Config, spec: TypPopulace) -> List[Agent]:
        return cls._build(config, spec)

    @classmethod
    def _build_balanced(
        cls,
        config: Config,
        strategies: List[tuple[str, Callable[[], Strategy]]],
        aggressive_only: bool = False,
    ) -> List[Agent]:
        rng = random.Random(config.seed)
        n_total = config.num_agents
        n_strategies = len(strategies)

        base_count = n_total // n_strategies
        remainder = n_total % n_strategies
        counts = [base_count + (1 if i < remainder else 0) for i in range(n_strategies)]
        max_count = max(counts) if counts else 0

        paired_budgets = [rng.uniform(*config.agent_budget_range) for _ in range(max_count)]
        agents: List[Agent] = []
        agent_idx = 0

        for strategy_idx, (_, strategy_factory) in enumerate(strategies):
            count = counts[strategy_idx]
            # pomer opatrnych se pocita uvnitr kazde strategicke skupiny
            cautious_count = 0 if aggressive_only else round(count * config.agent_cautious_ratio)
            for i in range(count):
                budget = paired_budgets[i]
                strategy = strategy_factory()
                agent_id = f"agent_{agent_idx:03d}"
                is_cautious = (i < cautious_count) and not aggressive_only
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

    @classmethod
    def _build(cls, config: Config, spec: TypPopulace) -> List[Agent]:
        rng = random.Random(config.seed)
        n_total = config.num_agents
        total_weight = sum(w for w, _, _ in spec)
        normalized = [(w / total_weight, sc, at) for w, sc, at in spec]

        agents: List[Agent] = []
        agent_idx = 0
        for weight, strategy_cls, agent_type in normalized:
            count = round(weight * n_total)
            for _ in range(count):
                if agent_idx >= n_total:
                    break
                budget = rng.uniform(*config.agent_budget_range)
                agent_id = f"agent_{agent_idx:03d}"
                if strategy_cls is HotColdStrategie:
                    strategy: Strategy = HotColdStrategie(mode="hot", candidate_pool_multiplier=config.hot_cold_pool_multiplier)
                elif strategy_cls is MartingaleStrategie:
                    strategy = MartingaleStrategie(base_tickets=1, max_tickets=config.martingale_max_tickets)
                else:
                    strategy = strategy_cls()

                if agent_type == "C":
                    agent: Agent = OpatrnyHrac(agent_id, budget, strategy, config.ticket_price)
                else:
                    agent = AgresivniHrac(agent_id, budget, strategy, config.ticket_price)
                agents.append(agent)
                agent_idx += 1

        while len(agents) < n_total:
            budget = rng.uniform(*config.agent_budget_range)
            agents.append(OpatrnyHrac(
                agent_id=f"agent_{agent_idx:03d}",
                initial_budget=budget,
                strategy=NahodnaStrategie(),
                ticket_price=config.ticket_price,
            ))
            agent_idx += 1
        return agents[:n_total]
