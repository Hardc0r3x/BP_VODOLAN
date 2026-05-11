from __future__ import annotations

# Soubor obsahuje Martingale strategii.
# Strategie zvysuje pocet tiketu po ztrate a resetuje az po pokryti deficitu.
from typing import List, TYPE_CHECKING

from base import Strategy

if TYPE_CHECKING:
    from base import Agent
    from loterie import Loterie


# martingale - po kazde prohre zdvojnasobi sazku (koupi 2x vic tiketu)
# sleduje kumulovanou ztratu (deficit) a kdyz se dostane na nulu, resetuje se
# v praxi na tohle lidi nemaji dost penez, ale chci to simulovat
class MartingaleStrategie(Strategy):

    def __init__(self, base_tickets: int = 1, max_tickets: int = 32) -> None:
        self._base_tickets = base_tickets      # kolik tiketu na zacatku
        self._max_tickets = max_tickets        # strop aby nekupoval stovky tiketu
        self._current_tickets = base_tickets   # aktualni pocet pro dalsi kolo
        self._consecutive_losses = 0           # kolik kol za sebou prohral
        self._deficit = 0.0                    # kumulovana ztrata od posledniho resetu

    @property
    def name(self) -> str:
        return "Martingale"

    def select_numbers(self, agent: "Agent", lottery: "Loterie") -> List[int]:
        # martingale meni pocet tiketu, ale cisla vybira nahodne
        return lottery.prng.draw_numbers(
            lottery.config.num_balls,
            lottery.config.draw_size,
        )

    def determine_num_tickets(self, agent: "Agent") -> int:
        # spocita kolik tiketu si hrac realne muze dovolit
        affordable = max(1, int(agent.budget // agent.ticket_price))
        # vybere mensi z: co chce strategie, strop, a co si hrac muze dovolit
        return min(self._current_tickets, self._max_tickets, affordable)

    def on_round_result(self, agent: "Agent", matches: int, prize: float, cost: float = 0.0) -> None:
        # prepocita deficit - kolik celkem trati od posledniho resetu
        self._deficit += float(cost) - float(prize)
        # kdyz se deficit dostal na nulu nebo do plusu, strategie se restartuje
        if self._deficit <= 0:
            self._deficit = 0.0
            self._current_tickets = self._base_tickets
            self._consecutive_losses = 0
            return
        # porad v minusu? pristi kolo zdvojnasob pocet tiketu
        self._consecutive_losses += 1
        self._current_tickets = min(self._current_tickets * 2, self._max_tickets)

    def reset(self) -> None:
        # pred novym MC behem vsechno zpet na zacatek
        self._current_tickets = self._base_tickets
        self._consecutive_losses = 0
        self._deficit = 0.0

    def __repr__(self) -> str:
        return (
            f"MartingaleStrategie(current_tickets={self._current_tickets}, "
            f"losses={self._consecutive_losses}, deficit={self._deficit:.2f})"
        )
