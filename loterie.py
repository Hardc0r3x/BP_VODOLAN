from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from config import Config
from prng import PRNG


class Loterie:

    def __init__(self, config: Config, draw_prng: PRNG, ticket_prng: PRNG | None = None) -> None:
        self._config = config
        self._draw_prng = draw_prng
        # pokud není zvlášť ticket PRNG, použije se stejný jako pro losování
        self._ticket_prng = ticket_prng if ticket_prng is not None else draw_prng

        self._current_round: int = 0
        self._drawn_numbers: Optional[List[int]] = None
        self._drawn_set: set[int] = set()  # set je rychlejší pro hledání shod

        # počítám jak často každé číslo padlo, pro HotCold strategii
        self._number_frequencies: Dict[int, int] = {
            i: 0 for i in range(1, config.num_balls + 1)
        }
        self._draw_history: List[List[int]] = []  # všechny tahy pro případnou analýzu

        self._jackpot: float = config.min_jackpot
        self._sorted_frequency_cache: Dict[str, List[int]] = {}  # cache aby se netřídilo každé kolo znova

    @property
    def config(self) -> Config:
        return self._config

    @property
    def prng(self) -> PRNG:
        return self._ticket_prng

    @property
    def draw_prng(self) -> PRNG:
        return self._draw_prng

    @property
    def ticket_prng(self) -> PRNG:
        return self._ticket_prng

    @property
    def current_round(self) -> int:
        return self._current_round

    @property
    def drawn_numbers(self) -> Optional[List[int]]:
        return self._drawn_numbers

    @property
    def number_frequencies(self) -> Dict[int, int]:
        return self._number_frequencies

    @property
    def jackpot(self) -> float:
        return self._jackpot

    @property
    def draw_history(self) -> List[List[int]]:
        return self._draw_history

    def numbers_sorted_by_frequency(self, mode: str) -> Optional[List[int]]:
        if mode not in {"hot", "cold"}:
            raise ValueError("mode musi byt 'hot' nebo 'cold'")
        # pokud ještě neproběhl žádný tah, nemáme frekvence
        if not any(self._number_frequencies.values()):
            return None
        if mode not in self._sorted_frequency_cache:
            numbers = list(range(1, self._config.num_balls + 1))
            # zamíchám před tříděním aby čísla se stejnou frekvencí byla v náhodném pořadí
            self._ticket_prng.shuffle(numbers)
            self._sorted_frequency_cache[mode] = sorted(
                numbers,
                key=lambda n: self._number_frequencies.get(n, 0),
                reverse=(mode == "hot"),  # hot = sestupně, cold = vzestupně
            )
        return self._sorted_frequency_cache[mode]

    def conduct_draw(self) -> List[int]:
        # samotné losování číslic pro toto kolo
        self._current_round += 1
        self._drawn_numbers = self._draw_prng.draw_numbers(
            self._config.num_balls, self._config.draw_size
        )
        self._drawn_set = set(self._drawn_numbers)  # pro rychlé porovnání s tikety
        self._draw_history.append(list(self._drawn_numbers))
        return self._drawn_numbers

    def commit_draw_frequencies(self) -> None:
        # aktualizace frekvencí až po vyhodnocení tiketů, ne hned po losování
        if self._drawn_numbers is None:
            return
        for n in self._drawn_numbers:
            self._number_frequencies[n] += 1
        self._sorted_frequency_cache.clear()  # cache je zastaralá, smazat

    def count_matches(self, ticket_numbers: List[int]) -> int:
        if self._drawn_numbers is None:
            raise RuntimeError("Kolo nebylo losovano. Nejdrive zavolej conduct_draw().")
        return sum(1 for n in ticket_numbers if n in self._drawn_set)

    def check_ticket(self, ticket_numbers: List[int], jackpot_share: float | None = None) -> Tuple[int, float]:
        matches = self.count_matches(ticket_numbers)
        prize = self.prize_for_matches(matches, jackpot_share=jackpot_share)
        return matches, prize

    def prize_for_matches(self, matches: int, jackpot_share: float | None = None) -> float:
        # jackpot se dělí pokud vyhrál víc hráčů ve stejném kole
        if matches == self._config.draw_size:
            return self._jackpot if jackpot_share is None else jackpot_share
        # fixni vyhry jsou jen pro 3, 4 a 5 shod podle configu
        return self._config.fixed_prizes.get(matches, 0.0)

    def update_jackpot(self, new_value: float) -> None:
        # loterie jen kopiruje hodnotu z provozovatele
        self._jackpot = float(new_value)

    def reset(self) -> None:
        # reset před dalším MC během
        self._current_round = 0
        self._drawn_numbers = None
        self._drawn_set = set()
        self._number_frequencies = {i: 0 for i in range(1, self._config.num_balls + 1)}
        self._draw_history.clear()
        self._jackpot = self._config.min_jackpot
        self._sorted_frequency_cache.clear()

    def __repr__(self) -> str:
        return f"Loterie(round={self._current_round}, jackpot={self._jackpot:,.0f} CZK)"
