from __future__ import annotations
from typing import List, TYPE_CHECKING

from base import Strategy

if TYPE_CHECKING:
    from base import Agent
    from loterie import Loterie


# Martingale sleduje deficit od posledniho resetu a podle nej zvysuje sazku
# strategie se resetuje az kdyz se deficit srovna na nulu nebo do plusu
class MartingaleStrategie(Strategy):

    def __init__(self, base_tickets: int = 1, max_tickets: int = 32) -> None:
        self._base_tickets = base_tickets      # vychozi pocet tiketu
        self._max_tickets = max_tickets        # strop aby hrac nekupoval moc tiketu
        self._current_tickets = base_tickets   # pocet tiketu pro dalsi kolo
        self._consecutive_losses = 0           # pocitadlo kol bez resetu
        self._deficit = 0.0                    # kumulovana ztrata od posledniho resetu

    @property
    def name(self) -> str:
        return "Martingale"

    def select_numbers(self, agent: "Agent", lottery: "Loterie") -> List[int]:
        # Martingale si cisla nevybira chytre, proste nahodne
        return lottery.prng.draw_numbers(
            lottery.config.num_balls,
            lottery.config.draw_size,
        )

    def determine_num_tickets(self, agent: "Agent") -> int:
        # spocita kolik tiketu si hrac muze dovolit
        affordable = max(1, int(agent.budget // agent.ticket_price))
        # vrati mensi hodnotu podle strategie, limitu a budgetu
        return min(self._current_tickets, self._max_tickets, affordable)

    def on_round_result(self, agent: "Agent", matches: int, prize: float, cost: float = 0.0) -> None:
        # oprava: deficit se pocita ze skutecne ceny a skutecne vyhry kola
        self._deficit += float(cost) - float(prize)
        # pokud je deficit splaceny, strategie se vrati na zacatek
        if self._deficit <= 0:
            self._deficit = 0.0
            self._current_tickets = self._base_tickets
            self._consecutive_losses = 0
            return
        # pokud deficit trva, dalsi kolo se sazka zdvojnasobi do limitu
        self._consecutive_losses += 1
        self._current_tickets = min(self._current_tickets * 2, self._max_tickets)

    def reset(self) -> None:
        # reset pred novym MC behem vrati pocet tiketu na zaklad
        self._current_tickets = self._base_tickets
        # reset musi vynulovat i pocitadlo neuspesnych kol
        self._consecutive_losses = 0
        # reset musi vynulovat i kumulovany deficit
        self._deficit = 0.0

    def __repr__(self) -> str:
        return (
            f"MartingaleStrategie(current_tickets={self._current_tickets}, "
            f"losses={self._consecutive_losses}, deficit={self._deficit:.2f})"
        )
