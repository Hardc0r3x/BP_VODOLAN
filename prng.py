from __future__ import annotations

from typing import List, Sequence

import numpy as np
import numpy.random as npr


# wrapper kolem numpy generátoru, aby se dalo snadno resetovat a seedovat
class PRNG:

    def __init__(self, seed: int | npr.SeedSequence = 42):
        self._seed_sequence = self._to_seed_sequence(seed)
        self._rng: npr.Generator = self._build_rng(self._seed_sequence)

    @staticmethod
    def _to_seed_sequence(seed: int | npr.SeedSequence) -> npr.SeedSequence:
        # SeedSequence umí "spawning" - z jednoho seedu odvozuje nezávislé proudy
        if isinstance(seed, npr.SeedSequence):
            return seed
        return npr.SeedSequence(int(seed))

    @staticmethod
    def _build_rng(seed_sequence: npr.SeedSequence) -> npr.Generator:
        # MT19937 je klasický Mersenne Twister, dostatečný pro simulace
        bit_generator = npr.MT19937(seed_sequence)
        return npr.Generator(bit_generator)

    def reset(self, seed: int | npr.SeedSequence | None = None) -> None:
        # reset na začátek sekvence, volá se před každým MC během
        if seed is not None:
            self._seed_sequence = self._to_seed_sequence(seed)
        self._rng = self._build_rng(self._seed_sequence)

    def draw_numbers(self, pool_size: int, draw_size: int) -> List[int]:
        if draw_size < 0:
            raise ValueError("draw_size nesmi byt zaporne")
        if draw_size > pool_size:
            raise ValueError("draw_size nesmi byt vetsi nez pool_size")
        if draw_size == 0:
            return []

        # trik přes argpartition - rychlejší než shuffle + slice pro velké pooly
        keys = self._rng.random(pool_size)
        idx = np.argpartition(keys, draw_size - 1)[:draw_size]
        idx.sort()  # seřazení indexů pro konzistentní výstup
        return [int(n) + 1 for n in idx]  # +1 protože čísla loterie začínají od 1

    def uniform(self, low: float = 0.0, high: float = 1.0) -> float:
        return float(self._rng.uniform(low, high))

    def randint(self, low: int, high: int) -> int:
        return int(self._rng.integers(low, high + 1))

    def choice(self, arr: Sequence, size: int = 1, replace: bool = False) -> np.ndarray:
        return self._rng.choice(arr, size=size, replace=replace)

    def shuffle(self, arr: list) -> None:
        self._rng.shuffle(arr)

    @property
    def seed(self) -> int:
        entropy = self._seed_sequence.entropy
        return int(entropy) if isinstance(entropy, int) else 0

    @property
    def seed_sequence(self) -> npr.SeedSequence:
        return self._seed_sequence

    def __repr__(self) -> str:
        return f"PRNG(entropy={self._seed_sequence.entropy!r}, spawn_key={self._seed_sequence.spawn_key})"
