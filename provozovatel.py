from __future__ import annotations
from typing import Dict, List, Any

from config import Config


# provozovatel loterie - spravuje kapital, vyplaci vyhry, hlida jestli nezkrachoval
# dulezite je ze kapital a jackpotovy fond jsou oddelene
class Provozovatel:

    def __init__(self, config: Config) -> None:
        self._config = config
        self._initial_capital = config.operator_initial_capital

        self._capital: float = self._initial_capital  # volne penize provozovatele
        self._jackpot_pool: float = config.min_jackpot  # oddelena rezerva na jackpot
        self._bankrupt: bool = False

        self._total_revenue: float = 0.0     # kolik celkem utrzil za tikety
        self._total_payouts: float = 0.0     # kolik celkem vyplatil
        self._rounds_operated: int = 0
        self._unpaid_liabilities: float = 0.0    # vyhry co neslo zaplatit
        self._largest_unpaid_prize: float = 0.0  # nejvetsi nezaplacena castka
        self._bankruptcy_round: int | None = None  # v jakem kole sel do bankrotu

        # historie po kolech - pouzije se v grafech
        self._capital_history: List[float] = []
        self._revenue_history: List[float] = []
        self._payout_history: List[float] = []

    @property
    def capital(self) -> float:
        return self._capital

    @property
    def is_bankrupt(self) -> bool:
        return self._bankrupt

    @property
    def jackpot_pool(self) -> float:
        return self._jackpot_pool

    @property
    def total_revenue(self) -> float:
        return self._total_revenue

    @property
    def total_payouts(self) -> float:
        return self._total_payouts

    @property
    def unpaid_liabilities(self) -> float:
        return self._unpaid_liabilities

    @property
    def profit_margin(self) -> float:
        if self._total_revenue == 0:
            return 0.0
        return (self._total_revenue - self._total_payouts) / self._total_revenue * 100

    @property
    def capital_history(self) -> List[float]:
        return self._capital_history

    def collect_revenue(self, num_tickets_sold: int) -> float:
        # trzba za prodane tikety v tomhle kole
        round_revenue = num_tickets_sold * self._config.ticket_price
        # cast jde do jackpotoveho fondu
        jackpot_share = round_revenue * self._config.prize_pool_ratio
        # zbytek je volny kapital provozovatele
        capital_share = round_revenue - jackpot_share
        self._capital += capital_share
        self._jackpot_pool += jackpot_share
        self._total_revenue += round_revenue
        return round_revenue

    def register_unpaid_prize(self, amount: float, current_round: int | None = None) -> None:
        # nema dost na vyplatu - zaznamenat dluh
        if amount <= 0:
            return
        self._bankrupt = True
        self._unpaid_liabilities += amount
        self._largest_unpaid_prize = max(self._largest_unpaid_prize, amount)
        if self._bankruptcy_round is None:
            self._bankruptcy_round = current_round

    def pay_prize(self, amount: float, current_round: int | None = None, is_jackpot: bool = False) -> bool:
        if amount <= 0:
            return True

        # mala tolerance kvuli desetinnym cislum
        eps = 0.000001

        if is_jackpot:
            # jackpotova vyhra se plati z jackpotoveho fondu
            # bankrot volneho kapitalu ji nema blokovat
            if self._jackpot_pool + eps < amount:
                self.register_unpaid_prize(amount, current_round=current_round)
                return False

            self._jackpot_pool = max(0.0, self._jackpot_pool - amount)
            self._total_payouts += amount
            return True

        # fixni vyhry se plati z volneho kapitalu
        # pokud je provozovatel v bankrotu nebo nema kapital, fixni vyhra se nevyplati
        if self._bankrupt or self._capital + eps < amount:
            self.register_unpaid_prize(amount, current_round=current_round)
            return False

        self._capital -= amount
        self._total_payouts += amount
        return True

    def top_up_jackpot_pool(self, current_round: int | None = None) -> bool:
        # po vyplatach dorovnat jackpot na minimum (pokud je z ceho)
        missing = self._config.min_jackpot - self._jackpot_pool
        if missing <= 0:
            return True
        # uz je v bankrotu, dorovnani se nezkousi
        if self._bankrupt:
            return False
        # kapital nestaci na dorovnani - bankrot
        if self._capital + 0.000001 < missing:
            self.register_unpaid_prize(missing, current_round=current_round)
            return False
        # presun penez z kapitalu do jackpotove rezervy
        self._capital -= missing
        self._jackpot_pool += missing
        return True

    def record_round(self, round_revenue: float, round_payouts: float) -> None:
        # ulozit historii kola pro grafy
        self._rounds_operated += 1
        self._capital_history.append(self._capital)
        self._revenue_history.append(round_revenue)
        self._payout_history.append(round_payouts)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initial_capital": self._initial_capital,
            "final_capital": self._capital,
            "jackpot_pool": self._jackpot_pool,
            "total_revenue": self._total_revenue,
            "total_payouts": self._total_payouts,
            "net_profit": self._capital - self._initial_capital,
            "profit_margin": self.profit_margin,
            "bankrupt": self._bankrupt,
            "rounds_operated": self._rounds_operated,
            "unpaid_liabilities": self._unpaid_liabilities,
            "largest_unpaid_prize": self._largest_unpaid_prize,
            "bankruptcy_round": self._bankruptcy_round,
        }

    def reset(self) -> None:
        # reset pred novym MC behem - vsechno zpet na puvodni stav
        self._capital = self._initial_capital
        self._jackpot_pool = self._config.min_jackpot
        self._bankrupt = False
        self._total_revenue = 0.0
        self._total_payouts = 0.0
        self._rounds_operated = 0
        self._unpaid_liabilities = 0.0
        self._largest_unpaid_prize = 0.0
        self._bankruptcy_round = None
        self._capital_history.clear()
        self._revenue_history.clear()
        self._payout_history.clear()

    def __repr__(self) -> str:
        status = "BANKRUPT" if self._bankrupt else "OK"
        return f"Provozovatel(capital={self._capital:,.0f} CZK, jackpot_pool={self._jackpot_pool:,.0f} CZK, status={status})"