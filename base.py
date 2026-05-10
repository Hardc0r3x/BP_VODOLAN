from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from loterie import Loterie


# zakladni trida hrace - vsichni hraci z ni dedi
# sama o sobe se pouzit neda, proste definuje co kazdy hrac musi umet
class Agent(ABC):

    def __init__(
        self,
        agent_id: str,
        initial_budget: float,
        strategy: "Strategy",
        ticket_price: float,
    ) -> None:
        self._id = agent_id
        self._initial_budget = initial_budget
        self._budget = initial_budget  # kolik ma prave ted - meni se kazde kolo
        self._strategy = strategy
        self._ticket_price = ticket_price

        self._total_spent: float = 0.0  # celkem utraceno za tikety
        self._total_won: float = 0.0    # celkem vyhrano
        self._rounds_played: int = 0    # pocet odehranych kol
        self._active: bool = True       # false = dosly mu penize, uz nehraje

        self._history: List[Dict[str, Any]] = []  # zaznam po kazdem kole

    @property
    def id(self) -> str:
        return self._id

    @property
    def budget(self) -> float:
        return self._budget

    @property
    def ticket_price(self) -> float:
        return self._ticket_price

    @property
    def strategy(self) -> "Strategy":
        return self._strategy

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def total_spent(self) -> float:
        return self._total_spent

    @property
    def total_won(self) -> float:
        return self._total_won

    @property
    def net_profit(self) -> float:
        # kladne = vydelal (coz se skoro nestane), zaporne = prodělal
        return self._total_won - self._total_spent

    @property
    def roi(self) -> float:
        if self._total_spent == 0:
            return 0.0
        # return on investment v procentech, skoro vzdy zaporne
        return self.net_profit / self._total_spent * 100

    @property
    def rounds_played(self) -> int:
        return self._rounds_played

    @property
    def history(self) -> List[Dict[str, Any]]:
        return self._history

    @property
    @abstractmethod
    def risk_profile(self) -> str:
        # podtridy vrati "agresivni" nebo "opatrny"
        ...

    @abstractmethod
    def should_play(self) -> bool:
        # kazdy typ hrace rozhodne sam jestli v tomhle kole hraje
        ...

    @abstractmethod
    def on_round_result(self, tickets_played: int, matches: int, prize: float) -> None:
        # co hrac udela po vysledku kola (martingale treba zdvojnasobi sazku)
        ...

    def place_bets(self, lottery: "Loterie") -> Optional[Dict[str, Any]]:
        # kontrola jestli hrac chce a muze hrat
        if not self._active or not self.should_play():
            return None

        # strategie urcuje pocet tiketu pro toto kolo
        num_tickets = self._strategy.determine_num_tickets(self)
        cost = num_tickets * self._ticket_price

        # nema na vsechny tikety? koupi kolik muze
        if cost > self._budget:
            num_tickets = max(1, int(self._budget // self._ticket_price))
            cost = num_tickets * self._ticket_price
        if cost > self._budget or num_tickets <= 0:
            self._active = False
            return None

        # pro kazdy tiket strategie vybere sadu cisel
        ticket_numbers = [
            self._strategy.select_numbers(self, lottery)
            for _ in range(num_tickets)
        ]

        # strhne cenu tiketu z budgetu
        self._budget -= cost
        self._total_spent += cost
        self._rounds_played += 1

        return {
            "round": lottery.current_round + 1,
            "tickets": num_tickets,
            "cost": cost,
            "ticket_numbers": ticket_numbers,
        }

    def resolve_bets(
        self,
        pending: Dict[str, Any],
        ticket_matches: List[int],
        ticket_prizes: List[float],
    ) -> Dict[str, Any]:
        best_matches = max(ticket_matches) if ticket_matches else 0
        total_prize = float(sum(ticket_prizes))
        cost = float(pending.get("cost", 0.0))
        num_tickets = int(pending.get("tickets", 0) or 0)

        # pricte vyhru zpet do budgetu
        self._budget += total_prize
        self._total_won += total_prize

        # da vedet strategii a hraci jak dopadlo kolo
        self._strategy.on_round_result(self, best_matches, total_prize, cost)
        self.on_round_result(num_tickets, best_matches, total_prize)

        # ulozi zaznam kola do historie pro pozdejsi analyzu
        record: Dict[str, Any] = {
            "round": pending.get("round"),
            "tickets": num_tickets,
            "cost": cost,
            "matches": best_matches,
            "prize": total_prize,
            "ticket_matches": ticket_matches,
            "ticket_prizes": ticket_prizes,
            "ticket_numbers": pending.get("ticket_numbers", []),
            "budget": self._budget,
        }
        self._history.append(record)
        return record

    def play_round(self, lottery: "Loterie") -> Optional[Dict[str, Any]]:
        # zkracena verze kde se losovani deje uvnitr
        pending = self.place_bets(lottery)
        if pending is None:
            return None
        ticket_matches: List[int] = []
        ticket_prizes: List[float] = []
        for numbers in pending["ticket_numbers"]:
            matches, prize = lottery.check_ticket(numbers)
            ticket_matches.append(matches)
            ticket_prizes.append(prize)
        return self.resolve_bets(pending, ticket_matches, ticket_prizes)

    def revoke_unpaid_prize(self, amount: float) -> None:
        # provozovatel nema na vyplatu - musime odecist co jsme uz prictli
        if amount <= 0:
            return
        self._budget -= amount
        self._total_won -= amount
        if self._history:
            self._history[-1]["unpaid_prize"] = amount
            self._history[-1]["prize"] = max(0.0, float(self._history[-1].get("prize", 0.0)) - amount)
            self._history[-1]["budget"] = self._budget

    def get_summary(self) -> Dict[str, Any]:
        # shrnuti pro statistiky, vola se na konci kazdeho MC behu
        skipped = int(getattr(self, "skipped_rounds", 0))
        return {
            "agent_id": self._id,
            "strategy": self._strategy.name,
            "type": self.__class__.__name__,
            "risk_profile": self.risk_profile,
            "initial_budget": self._initial_budget,
            "final_budget": self._budget,
            "total_spent": self._total_spent,
            "total_won": self._total_won,
            "net_profit": self.net_profit,
            "roi": self.roi,
            "rounds_played": self._rounds_played,
            "skipped_rounds": skipped,
            "active": self._active,
            "actual_bankrupt": self._budget < self._ticket_price,  # nema ani na jeden tiket
            "history": self._history,
        }

    def reset(self, new_budget: Optional[float] = None) -> None:
        # reset na zacatek pred dalsim MC behem
        self._budget = new_budget if new_budget is not None else self._initial_budget
        self._total_spent = 0.0
        self._total_won = 0.0
        self._rounds_played = 0
        self._active = True
        self._history.clear()
        self._strategy.reset()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id={self._id!r}, "
            f"strategy={self._strategy.name!r}, budget={self._budget:.0f} CZK)"
        )


# zakladni trida pro sazkove strategie
# kazda strategie musi umet vybrat cisla a urcit pocet tiketu
class Strategy(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def select_numbers(self, agent: "Agent", lottery: "Loterie") -> List[int]:
        # vrati seznam cisel na jeden tiket
        ...

    @abstractmethod
    def determine_num_tickets(self, agent: "Agent") -> int:
        # vrati kolik tiketu hrac koupí v tomhle kole
        ...

    def on_round_result(self, agent: "Agent", matches: int, prize: float, cost: float = 0.0) -> None:
        # vetsina strategii na vysledek nereaguje, ale treba martingale ano
        pass

    def reset(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
