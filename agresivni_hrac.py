from __future__ import annotations
from typing import TYPE_CHECKING

from base import Agent

if TYPE_CHECKING:
    from base import Strategy


# agresivni hrac - hraje porad dokud ma na tiket, nikdy nepauznuje
class AgresivniHrac(Agent):

    def __init__(
        self,
        agent_id: str,
        initial_budget: float,
        strategy: "Strategy",
        ticket_price: float,
    ) -> None:
        super().__init__(agent_id, initial_budget, strategy, ticket_price)
        self._consecutive_wins: int = 0    # kolik vyher za sebou
        self._on_winning_streak: bool = False

    @property
    def risk_profile(self) -> str:
        return "agresivni"

    def should_play(self) -> bool:
        # proste hraje dokud nema prazdno
        if self._budget < self._ticket_price:
            self._active = False
            return False
        return True

    def on_round_result(self, tickets_played: int, matches: int, prize: float) -> None:
        if prize > 0:
            self._consecutive_wins += 1
            self._on_winning_streak = True
        else:
            # prohra prerusi serii
            self._consecutive_wins = 0
            self._on_winning_streak = False

    @property
    def is_on_streak(self) -> bool:
        return self._on_winning_streak

    @property
    def consecutive_wins(self) -> int:
        return self._consecutive_wins

    def reset(self, new_budget: float | None = None) -> None:
        super().reset(new_budget)
        # vynulovat serii pri novem MC behu
        self._consecutive_wins = 0
        self._on_winning_streak = False
