from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import comb, exp
from typing import Dict, Tuple


# výchozí hodnoty pro loterii 6/49
LOTTERY_NAME: str = "Obecna ciselna loterie (6/49)"

NUM_BALLS: int = 49   # celkem čísel v loterii
DRAW_SIZE: int = 6    # kolik čísel se táhne
TICKET_PRICE: float = 20.0  # cena jednoho tiketu v Kč

PRIZE_POOL_RATIO: float = 0.50  # polovina trzeb jde do jackpotoveho poolu

# fixní výhry pro nižší kategorie, jackpot se počítá dynamicky
FIXED_PRIZES: Dict[int, float] = {
    3: 100.0,
    4: 1_000.0,
    5: 50_000.0,
}

JACKPOT_ROLLOVER: bool = True         # jackpot se přenáší do dalšího kola pokud nikdo nevyhrál
MIN_JACKPOT: float = 1_000_000.0      # garantované minimum jackpotu
OPERATOR_INITIAL_CAPITAL: float = 10_000_000.0  # startovní kapitál provozovatele

NUM_AGENTS: int = 100
AGENT_BUDGET_RANGE: Tuple[float, float] = (500.0, 5_000.0)  # rozpětí počátečních budgetů hráčů
AGENT_CAUTIOUS_RATIO: float = 0.50  # polovina hracu je opatrna v kazde strategii
HOT_COLD_POOL_MULTIPLIER: int = 3  # kolikrat vetsi kandidatni pool bere HotCold
MARTINGALE_MAX_TICKETS: int = 16  # maximalni pocet tiketu pro Martingale

AGENT_STRATEGY_MIX: Dict[str, float] = {
    "random": 0.35,
    "fixed": 0.30,
    "martingale": 0.20,
    "hot_cold": 0.15,
}

NUM_ROUNDS: int = 52        # jedno "roční" kolo = 52 týdenních tahů
NUM_SIMULATIONS: int = 1_000
SEED: int = 42


@dataclass
class Config:
    lottery_name: str = LOTTERY_NAME

    num_balls: int = NUM_BALLS
    draw_size: int = DRAW_SIZE
    ticket_price: float = TICKET_PRICE

    prize_pool_ratio: float = PRIZE_POOL_RATIO
    fixed_prizes: Dict[int, float] = field(default_factory=lambda: dict(FIXED_PRIZES))

    jackpot_rollover: bool = JACKPOT_ROLLOVER
    min_jackpot: float = MIN_JACKPOT
    operator_initial_capital: float = OPERATOR_INITIAL_CAPITAL

    num_agents: int = NUM_AGENTS
    agent_budget_range: Tuple[float, float] = field(default_factory=lambda: AGENT_BUDGET_RANGE)
    agent_cautious_ratio: float = AGENT_CAUTIOUS_RATIO
    hot_cold_pool_multiplier: int = HOT_COLD_POOL_MULTIPLIER
    martingale_max_tickets: int = MARTINGALE_MAX_TICKETS
    agent_strategy_mix: Dict[str, float] = field(default_factory=lambda: dict(AGENT_STRATEGY_MIX))

    num_rounds: int = NUM_ROUNDS
    num_simulations: int = NUM_SIMULATIONS
    seed: int = SEED

    def __post_init__(self) -> None:
        # základní validace parametrů při vytvoření konfigurace
        if self.draw_size >= self.num_balls:
            raise ValueError("draw_size musi byt mensi nez num_balls")
        if not (0 < self.prize_pool_ratio <= 1):
            raise ValueError("prize_pool_ratio musi byt v intervalu (0, 1]")
        if self.num_simulations <= 0:
            raise ValueError("num_simulations musi byt kladne")
        if self.num_rounds <= 0:
            raise ValueError("num_rounds musi byt kladne")
        if self.num_agents <= 0:
            raise ValueError("num_agents musi byt kladne")
        if not (0 <= self.agent_cautious_ratio <= 1):
            raise ValueError("agent_cautious_ratio musi byt v intervalu 0 az 1")
        if self.hot_cold_pool_multiplier <= 0:
            raise ValueError("hot_cold_pool_multiplier musi byt kladne")
        if self.martingale_max_tickets <= 0:
            raise ValueError("martingale_max_tickets musi byt kladne")

    @staticmethod
    def profile(name: str) -> "Config":
        # zkratky pro různé úrovně simulace
        key = name.lower().replace("_", "-")
        base = Config()
        if key == "quick":
            return replace(base, num_simulations=100)
        if key == "thesis":
            return replace(base, num_simulations=1_000)
        if key in {"deep", "deep-baseline"}:
            return replace(base, num_simulations=10_000)
        raise ValueError(f"Neznamy profil: {name}")

    def jackpot_probability(self) -> float:
        # C(49,6) = 13 983 816 kombinací
        return 1.0 / comb(self.num_balls, self.draw_size)

    def match_probability(self, k: int) -> float:
        # hypergeometrické rozdělení - pravděpodobnost přesně k shod
        n, N = self.draw_size, self.num_balls
        if k < 0 or k > n:
            return 0.0
        return comb(n, k) * comb(N - n, n - k) / comb(N, n)

    def expected_prize_per_ticket(self) -> float:
        # střední hodnota výhry na jeden tiket
        ev = self.min_jackpot * self.jackpot_probability()
        for k, prize in self.fixed_prizes.items():
            ev += prize * self.match_probability(k)
        return ev

    def theoretical_rtp(self) -> float:
        # Return to Player v procentech - kolik % vsazených peněz se průměrně vrátí
        return self.expected_prize_per_ticket() / self.ticket_price * 100

    def expected_value_per_ticket(self) -> float:
        # záporné číslo = hráč průměrně tratí tolik za každý tiket
        return self.expected_prize_per_ticket() - self.ticket_price

    def expected_jackpots(self, total_tickets: int | float) -> float:
        return float(total_tickets) * self.jackpot_probability()

    def probability_no_jackpot(self, total_tickets: int | float) -> float:
        # Poissonova aproximace - pravděpodobnost že jackpot vůbec nenastane
        return exp(-self.expected_jackpots(total_tickets))

    def jackpot_diagnostics(self, total_tickets: int | float) -> dict:
        expected = self.expected_jackpots(total_tickets)
        p_zero = self.probability_no_jackpot(total_tickets)
        return {
            "total_tickets": float(total_tickets),
            "jackpot_probability": self.jackpot_probability(),
            "jackpot_odds": 1 / self.jackpot_probability(),
            "expected_jackpots": expected,
            "probability_no_jackpot": p_zero,
            "probability_at_least_one_jackpot": 1 - p_zero,
        }

    def summary_str(self) -> str:
        mix_text = "20 % Nahodna, 20 % FixedCisla, 20 % Martingale, 20 % HotCold_hot, 20 % HotCold_cold"
        lines = [
            f"  Loterie: {self.lottery_name}",
            f"  Format: {self.draw_size}/{self.num_balls}",
            f"  Cena tiketu: {self.ticket_price:.0f} CZK",
            f"  Minimalni jackpot: {self.min_jackpot:,.0f} CZK",
            f"  P(jackpot): 1 / {comb(self.num_balls, self.draw_size):,.0f}",
            f"  Teoreticke RTP modelu: {self.theoretical_rtp():.2f} %",
            f"  EV tiketu: {self.expected_value_per_ticket():.2f} CZK",
            f"  Pocet agentu: {self.num_agents}",
            f"  Mix strategii baseline: {mix_text}",
            f"  Mix typu: {self.agent_cautious_ratio * 100:.0f} % opatrnych / {(1 - self.agent_cautious_ratio) * 100:.0f} % agresivnich",
            f"  Kol na beh: {self.num_rounds}",
            f"  MC behu: {self.num_simulations}",
            f"  Seed: {self.seed}",
        ]
        return "\n".join(lines)
