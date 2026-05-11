from __future__ import annotations

# Soubor obsahuje strategii hot/cold.
# Strategie vybira z cisel podle minulych frekvenci, ne podle aktualniho tahu.
from typing import List, TYPE_CHECKING

from base import Strategy

if TYPE_CHECKING:
    from base import Agent
    from loterie import Loterie


# strategie co sazi na cisla ktera padaji nejcasteji (hot) nebo nejmene (cold)
# v realite je to samozrejme nesmysl, protoze tahani je nezavisle,
# ale chci videt jestli to v simulaci neco zmeni oproti nahodne strategii
class HotColdStrategie(Strategy):

    def __init__(self, mode: str = "hot", candidate_pool_multiplier: int = 3) -> None:
        if mode not in ("hot", "cold"):
            raise ValueError("mode musi byt 'hot' nebo 'cold'")
        self._mode = mode
        self._multiplier = candidate_pool_multiplier  # bere top N*draw_size cisel jako kandidaty

    @property
    def name(self) -> str:
        return f"HotCold_{self._mode}"

    def select_numbers(self, agent: "Agent", lottery: "Loterie") -> List[int]:
        draw_size = lottery.config.draw_size
        num_balls = lottery.config.num_balls

        sorted_numbers = lottery.numbers_sorted_by_frequency(self._mode)
        if sorted_numbers is None:
            # v prvnim kole nemame zadne frekvence, tak pouzijeme nahodny vyber
            return lottery.prng.draw_numbers(num_balls, draw_size)

        # vytvori pool z top (draw_size * multiplier) cisel
        # a z nich nahodne vybere draw_size cisel na tiket
        # takhle nehraji vsichni hotcold hraci uplne stejna cisla
        pool_size = min(draw_size * self._multiplier, num_balls)
        candidates = sorted_numbers[:pool_size]
        chosen = lottery.prng.choice(candidates, size=draw_size, replace=False)
        return sorted(int(n) for n in chosen)

    def determine_num_tickets(self, agent: "Agent") -> int:
        return 1
