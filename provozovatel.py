from __future__ import annotations
from typing import Dict, List, Any

from config import Config


# modeluje provozovatele loterie a oddeluje volny kapital od jackpotu
class Provozovatel:

    def __init__(self, config: Config) -> None:
        self._config = config
        self._initial_capital = config.operator_initial_capital

        self._capital: float = self._initial_capital  # volny kapital provozovatele
        self._jackpot_pool: float = config.min_jackpot  # oddelena jackpotova rezerva
        self._bankrupt: bool = False

        self._total_revenue: float = 0.0     # celkove prijmy z prodeje tiketu
        self._total_payouts: float = 0.0     # celkove vyplaty vyher
        self._rounds_operated: int = 0
        self._unpaid_liabilities: float = 0.0    # vyhry nebo dorovnani co neslo zaplatit
        self._largest_unpaid_prize: float = 0.0  # nejvetsi nezaplacena castka
        self._bankruptcy_round: int | None = None  # v jakem kole zkrachoval

        # historie pro grafy
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
        # spocitame trzbu za prodane tikety
        round_revenue = num_tickets_sold * self._config.ticket_price
        # cast trzby jde do jackpotove rezervy
        jackpot_share = round_revenue * self._config.prize_pool_ratio
        # zbytek trzby je volny kapital provozovatele
        capital_share = round_revenue - jackpot_share
        # volny kapital se zvysi jen o svou cast trzby
        self._capital += capital_share
        # jackpotovy pool se zvysi o svoji cast trzby
        self._jackpot_pool += jackpot_share
        # celkove trzby zustavaji cele trzby z tiketu
        self._total_revenue += round_revenue
        return round_revenue

    def register_unpaid_prize(self, amount: float, current_round: int | None = None) -> None:
        # nema dost penez na vyplatu nebo dorovnani jackpotu
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
        if is_jackpot:
            # jackpotova vyhra se plati jen z jackpotove rezervy
            if self._bankrupt or self._jackpot_pool + 0.000001 < amount:
                self.register_unpaid_prize(amount, current_round=current_round)
                return False
            self._jackpot_pool = max(0.0, self._jackpot_pool - amount)
            self._total_payouts += amount
            return True
        # fixni vyhry se plati z volneho kapitalu
        if self._bankrupt or self._capital < amount:
            self.register_unpaid_prize(amount, current_round=current_round)
            return False
        self._capital -= amount
        self._total_payouts += amount
        return True

    def top_up_jackpot_pool(self, current_round: int | None = None) -> bool:
        # dorovnani se dela az po vyplatach v kole
        missing = self._config.min_jackpot - self._jackpot_pool
        if missing <= 0:
            return True
        # pokud uz je bankrot, dalsi dorovnani se nezkousi
        if self._bankrupt:
            return False
        # pokud kapital nestaci, provozovatel zkrachuje
        if self._capital < missing:
            self.register_unpaid_prize(missing, current_round=current_round)
            return False
        # presuneme chybejici cast z kapitalu do jackpotove rezervy
        self._capital -= missing
        self._jackpot_pool += missing
        return True

    def record_round(self, round_revenue: float, round_payouts: float) -> None:
        # uklada historii kazdeho kola pro grafy
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
        # reset pred dalsim MC behem
        self._capital = self._initial_capital
        # na zacatku behu se jackpotovy pool nastavi na minimum
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
