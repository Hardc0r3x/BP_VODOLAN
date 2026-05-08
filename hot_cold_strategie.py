from __future__ import annotations
from typing import List, TYPE_CHECKING

from base import Strategy

if TYPE_CHECKING:
    from base import Agent
    from loterie import Loterie


# strategie která sází na čísla co padají nejčastěji (hot) nebo nejméně (cold)
# v loterii je to samozřejmě nesmysl protože tahání je nezávislé, ale chci otestovat
# jestli to nějak ovlivní výsledky ve srovnání s čistě náhodnou strategií
class HotColdStrategie(Strategy):

    def __init__(self, mode: str = "hot", candidate_pool_multiplier: int = 3) -> None:
        if mode not in ("hot", "cold"):
            raise ValueError("mode musi byt 'hot' nebo 'cold'")
        self._mode = mode
        self._multiplier = candidate_pool_multiplier  # bere top N krat draw_size cisel jako kandidaty

    @property
    def name(self) -> str:
        return f"HotCold_{self._mode}"

    def select_numbers(self, agent: "Agent", lottery: "Loterie") -> List[int]:
        draw_size = lottery.config.draw_size
        num_balls = lottery.config.num_balls

        sorted_numbers = lottery.numbers_sorted_by_frequency(self._mode)
        if sorted_numbers is None:
            # první kolo - žádné frekvence ještě nejsou, fallback na náhodu
            return lottery.prng.draw_numbers(num_balls, draw_size)

        # vezme top (draw_size * multiplier) čísel jako kandidátský pool
        # a z nich náhodně vybere draw_size čísel
        pool_size = min(draw_size * self._multiplier, num_balls)
        candidates = sorted_numbers[:pool_size]
        chosen = lottery.prng.choice(candidates, size=draw_size, replace=False)
        return sorted(int(n) for n in chosen)

    def determine_num_tickets(self, agent: "Agent") -> int:
        return 1
