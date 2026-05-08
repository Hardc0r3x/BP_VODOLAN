from __future__ import annotations
from typing import List, TYPE_CHECKING

from base import Strategy

if TYPE_CHECKING:
    from base import Agent
    from loterie import Loterie


# referenční strategie - čistě náhodný výběr čísel každé kolo
# slouží jako baseline pro porovnání ostatních strategií
class NahodnaStrategie(Strategy):

    @property
    def name(self) -> str:
        return "Nahodna"

    def select_numbers(self, agent: "Agent", lottery: "Loterie") -> List[int]:
        # každé kolo jiná náhodná čísla
        return lottery.prng.draw_numbers(
            lottery.config.num_balls,
            lottery.config.draw_size,
        )

    def determine_num_tickets(self, agent: "Agent") -> int:
        return 1
