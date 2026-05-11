from __future__ import annotations

# Soubor definuje agresivni typ hrace.
# Tento hrac hraje dokud ma penize alespon na jeden tiket.
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

    @property
    def risk_profile(self) -> str:
        return "agresivni"

    def should_play(self) -> bool:
        # hraje, dokud ma penize alespon na jeden tiket
        if self._budget < self._ticket_price:
            self._active = False
            return False
        return True

    def on_round_result(self, tickets_played: int, matches: int, prize: float) -> None:
        # agresivni hrac na vysledek nijak nereaguje
        pass
