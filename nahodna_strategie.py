from __future__ import annotations
from typing import List, TYPE_CHECKING

from base import Strategy

if TYPE_CHECKING:
    from base import Agent
    from loterie import Loterie


# nahodna strategie - cisla se vybíraji uplne nahodne kazde kolo
# pouziva se hlavne jako baseline pro porovnani s ostatnima
class NahodnaStrategie(Strategy):

    @property
    def name(self) -> str:
        return "Nahodna"

    def select_numbers(self, agent: "Agent", lottery: "Loterie") -> List[int]:
        # kazde kolo nahodne vylosuje novy set cisel
        return lottery.prng.draw_numbers(
            lottery.config.num_balls,
            lottery.config.draw_size,
        )

    def determine_num_tickets(self, agent: "Agent") -> int:
        return 1
