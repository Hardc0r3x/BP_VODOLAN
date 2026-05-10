from __future__ import annotations
from typing import TYPE_CHECKING

from base import Agent

if TYPE_CHECKING:
    from base import Strategy


# opatrny hrac - pokud mu klesne budget pod bezpecnostni hranici, prestane sazet
# v zaznamech zustava, ale bez dalsi vyhry se uz vetsinou nevrati do hry
class OpatrnyHrac(Agent):

    def __init__(
        self,
        agent_id: str,
        initial_budget: float,
        strategy: "Strategy",
        ticket_price: float,
        safety_threshold: float = 0.20,  # hraje jen kdyz ma vic nez 20 % puvodniho rozpoctu
        min_reserve: float = 100.0,      # absolutni minimum - pod tim se oznaci jako neaktivni
    ) -> None:
        super().__init__(agent_id, initial_budget, strategy, ticket_price)
        self._safety_threshold = safety_threshold
        self._min_reserve = min_reserve
        self._skipped_rounds: int = 0  # kolikrat nehral kvuli nizkemu rozpoctu

    @property
    def risk_profile(self) -> str:
        return "opatrny"

    def should_play(self) -> bool:
        # pod absolutnim minimem konci uplne
        if self._budget < self._min_reserve:
            self._active = False
            return False

        # pod 20 % puvodniho rozpoctu uz dalsi tiket nekupuje
        relative_ok = self._budget >= self._initial_budget * self._safety_threshold
        if not relative_ok:
            self._skipped_rounds += 1
            return False

        return True

    def on_round_result(self, tickets_played: int, matches: int, prize: float) -> None:
        # opatrny hrac na vysledek nijak nereaguje
        pass

    @property
    def skipped_rounds(self) -> int:
        return self._skipped_rounds

    def reset(self, new_budget=None) -> None:
        super().reset(new_budget)
        self._skipped_rounds = 0
