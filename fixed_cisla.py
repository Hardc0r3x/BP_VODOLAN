from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING

from base import Strategy

if TYPE_CHECKING:
    from base import Agent
    from loterie import Loterie


# strategie kde hráč hraje pořád stejná čísla - jako ti co mají "šťastná čísla"
class FixedCisla(Strategy):

    def __init__(self, fixed_numbers: Optional[List[int]] = None) -> None:
        self._preset_numbers: Optional[List[int]] = fixed_numbers  # čísla zadaná zvenku
        self._fixed_numbers: Optional[List[int]] = fixed_numbers
        self._initialized: bool = fixed_numbers is not None

    @property
    def name(self) -> str:
        return "FixedCisla"

    def select_numbers(self, agent: "Agent", lottery: "Loterie") -> List[int]:
        if not self._initialized:
            # při prvním kole si náhodně vybere čísla a pak je drží celou simulaci
            self._fixed_numbers = lottery.prng.draw_numbers(
                lottery.config.num_balls,
                lottery.config.draw_size,
            )
            self._initialized = True
        return list(self._fixed_numbers)  # type: ignore[return-value]

    def determine_num_tickets(self, agent: "Agent") -> int:
        return 1

    def reset(self) -> None:
        # při resetu se vrátí na přednastavená čísla (nebo se znovu náhodně vybere v 1. kole)
        if self._preset_numbers is not None:
            self._fixed_numbers = list(self._preset_numbers)
            self._initialized = True
        else:
            self._fixed_numbers = None
            self._initialized = False
