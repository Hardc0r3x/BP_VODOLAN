from __future__ import annotations
from typing import TYPE_CHECKING

from base import Agent

if TYPE_CHECKING:
    from base import Strategy


# opatrný hráč kolo přeskočí pokud mu klesl budget moc nízko
class OpatrnyHrac(Agent):

    def __init__(
        self,
        agent_id: str,
        initial_budget: float,
        strategy: "Strategy",
        ticket_price: float,
        safety_threshold: float = 0.20,  # hraje jen pokud má víc než 20 % původního budgetu
        min_reserve: float = 100.0,      # absolutní minimum, pod tím se přestane hrát úplně
    ) -> None:
        super().__init__(agent_id, initial_budget, strategy, ticket_price)
        self._safety_threshold = safety_threshold
        self._min_reserve = min_reserve
        self._skipped_rounds: int = 0  # kolikrát přeskočil kolo kvůli nízkému budgetu

    @property
    def risk_profile(self) -> str:
        return "opatrny"

    def should_play(self) -> bool:
        # absolutní minimum - pod tím se deaktivuje natrvalo
        if self._budget < self._min_reserve:
            self._active = False
            return False

        # relativní minimum - pod 20 % původního budgetu přeskočí kolo, ale neskončí
        relative_ok = self._budget >= self._initial_budget * self._safety_threshold
        if not relative_ok:
            self._skipped_rounds += 1
            return False

        return True

    def on_round_result(self, tickets_played: int, matches: int, prize: float) -> None:
        # opatrný hráč na výsledek nereaguje, prostě čeká na příští kolo
        pass

    @property
    def skipped_rounds(self) -> int:
        return self._skipped_rounds

    def reset(self, new_budget=None) -> None:
        super().reset(new_budget)
        self._skipped_rounds = 0
