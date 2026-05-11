from __future__ import annotations

# Soubor obsahuje strategii s pevne zvolenymi cisly.
# Hrac si cisla vybere jednou a pak je opakuje.
from typing import List, Optional, TYPE_CHECKING

from base import Strategy

if TYPE_CHECKING:
    from base import Agent
    from loterie import Loterie


# strategie "stastna cisla" - hrac si jednou vybere cisla a pak je hraje porad dokola
# hodne lidi v realite hraje takhle, tak jsem to chtel otestovat
class FixedCisla(Strategy):

    def __init__(self, fixed_numbers: Optional[List[int]] = None) -> None:
        self._preset_numbers: Optional[List[int]] = fixed_numbers  # cisla zadana zvenku
        self._fixed_numbers: Optional[List[int]] = fixed_numbers
        self._initialized: bool = fixed_numbers is not None

    @property
    def name(self) -> str:
        return "FixedCisla"

    def select_numbers(self, agent: "Agent", lottery: "Loterie") -> List[int]:
        if not self._initialized:
            # v prvnim kole si nahodne vybere cisla a pak uz je drzi celou simulaci
            self._fixed_numbers = lottery.prng.draw_numbers(
                lottery.config.num_balls,
                lottery.config.draw_size,
            )
            self._initialized = True
        return list(self._fixed_numbers)  # type: ignore[return-value]

    def determine_num_tickets(self, agent: "Agent") -> int:
        return 1

    def reset(self) -> None:
        # pri resetu se vrati na puvodni cisla (nebo si v 1. kole vybere nova)
        if self._preset_numbers is not None:
            self._fixed_numbers = list(self._preset_numbers)
            self._initialized = True
        else:
            self._fixed_numbers = None
            self._initialized = False
