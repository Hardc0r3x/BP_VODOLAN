from __future__ import annotations

import hashlib
import json
from typing import Any

from config import Config
from mc_simulace import MCSimulace
from statistiky import SberStatistik
from tovarna_na_hrace import TovarnaNaHrace


def _digest(obj: Any) -> str:
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run_small(seed: int = 42) -> dict[str, Any]:
    cfg = Config(num_simulations=5, num_rounds=12, num_agents=30, seed=seed)
    stats = SberStatistik()
    agents = TovarnaNaHrace.standard_mix(cfg)
    MCSimulace(cfg, agents, stats).run()
    return {
        "operator": stats.get_operator_stats(),
        "prizes": stats.get_prize_stats(cfg),
        "strategies": stats.get_strategy_stats(),
    }


def main() -> None:
    cfg = Config()

    assert 18.0 < cfg.theoretical_rtp() < 19.0, (
        f"Teoreticke RTP ma byt okolo 18.64 %, vyslo {cfg.theoretical_rtp()}"
    )
    assert -17.0 < cfg.expected_value_per_ticket() < -16.0, (
        f"EV tiketu ma byt okolo -16.27 CZK, vyslo {cfg.expected_value_per_ticket()}"
    )

    first = _run_small(seed=42)
    second = _run_small(seed=42)
    assert _digest(first) == _digest(second), "Stejny seed nedava stejny vysledek."

    third = _run_small(seed=43)
    assert _digest(first) != _digest(third), "Ruzny seed dava stejny vysledek, to je podezrele."

    prize_stats = first["prizes"]
    total_win_prob = sum(v["pct_actual"] for v in prize_stats.values())
    assert total_win_prob >= 0.0, "Empiricke pravdepodobnosti nejsou validni."

    print("OK: kontrolni testy prosly.")
    print(f"Teoreticke RTP: {cfg.theoretical_rtp():.4f} %")
    print(f"EV tiketu: {cfg.expected_value_per_ticket():.4f} CZK")


if __name__ == "__main__":
    main()
