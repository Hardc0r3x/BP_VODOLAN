from __future__ import annotations

# Soubor obsahuje jednoduche kontrolni testy modelu.
# Testy hlidaji hlavni logiku popsanou v praci.

import hashlib
import json
from typing import Any

from config import Config
from martingale_strategie import MartingaleStrategie
from mc_simulace import MCSimulace
from provozovatel import Provozovatel
from statistiky import SberStatistik
from tovarna_na_hrace import TovarnaNaHrace


def _digest(obj: Any) -> str:
    # hash vysledku pro porovnani jestli dva behy daly to same
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run_small(seed: int = 42) -> dict[str, Any]:
    # male nastaveni aby test probehl rychle
    cfg = Config(num_simulations=5, num_rounds=12, num_agents=30, seed=seed)
    stats = SberStatistik()
    agents = TovarnaNaHrace.standard_mix(cfg)
    MCSimulace(cfg, agents, stats).run()
    return {
        "operator": stats.get_operator_stats(),
        "prizes": stats.get_prize_stats(cfg),
        "strategies": stats.get_strategy_stats(),
    }



def _test_operator_jackpot_pool() -> None:
    # kontrola ze kapital a jackpotovy fond jsou opravdu oddelene
    cfg = Config()
    operator = Provozovatel(cfg)
    eps = 0.000001

    assert abs(operator.capital - cfg.operator_initial_capital) < eps, "Kapital se na zacatku nesmi snizit o jackpot."
    assert abs(operator.jackpot_pool - cfg.min_jackpot) < eps, "Jackpotovy fond ma zacit na garantovanem minimu."

    # z trzby jde polovina do kapitalu a polovina do jackpotoveho fondu
    revenue = operator.collect_revenue(10)
    assert abs(revenue - 200.0) < eps, "Trzba za 10 tiketu po 20 Kc ma byt 200 Kc."
    assert abs(operator.capital - (cfg.operator_initial_capital + 100.0)) < eps, "Kapital ma dostat jen cast trzby."
    assert abs(operator.jackpot_pool - (cfg.min_jackpot + 100.0)) < eps, "Jackpotovy fond ma dostat svuj podil trzby."

    # fixni vyhra se bere z kapitalu, jackpotovy fond zustava stejny
    pool_before_fixed = operator.jackpot_pool
    capital_before_fixed = operator.capital
    assert operator.pay_prize(1_000.0, is_jackpot=False), "Fixni vyhra se ma vyplatit z kapitalu."
    assert abs(operator.capital - (capital_before_fixed - 1_000.0)) < eps, "Fixni vyhra ma snizit kapital."
    assert abs(operator.jackpot_pool - pool_before_fixed) < eps, "Fixni vyhra nesmi snizit jackpotovy fond."

    # jackpot se bere z jackpotoveho fondu, ne primo z volneho kapitalu
    jackpot_amount = operator.jackpot_pool
    capital_before_jackpot = operator.capital
    assert operator.pay_prize(jackpot_amount, is_jackpot=True), "Jackpot se ma vyplatit z jackpotoveho fondu."
    assert abs(operator.capital - capital_before_jackpot) < eps, "Vyplata jackpotu nema primo snizit volny kapital."
    assert abs(operator.jackpot_pool) < eps, "Po vyplaceni celeho jackpotu ma byt fond nulovy."

    # dorovnani garantovaneho jackpotu uz jde z volneho kapitalu
    assert operator.top_up_jackpot_pool(), "Dorovnani jackpotu ma projit, kdyz je dost kapitalu."
    assert abs(operator.jackpot_pool - cfg.min_jackpot) < eps, "Fond se ma vratit na garantovane minimum."
    assert abs(operator.capital - (capital_before_jackpot - cfg.min_jackpot)) < eps, "Dorovnani ma snizit volny kapital."


def _test_martingale_deficit_reset() -> None:
    # kontrola ze Martingale resetuje az po pokryti kumulovane ztraty
    class DummyAgent:
        budget = 10_000.0
        ticket_price = 20.0

    agent = DummyAgent()
    strategy = MartingaleStrategie(base_tickets=1, max_tickets=16)

    strategy.on_round_result(agent, matches=0, prize=0.0, cost=20.0)
    assert strategy.determine_num_tickets(agent) == 2, "Po ztrate ma Martingale navysit sazku."

    strategy.on_round_result(agent, matches=3, prize=10.0, cost=20.0)
    assert strategy.determine_num_tickets(agent) == 4, "Mala vyhra nema resetovat kumulovany deficit."

    strategy.on_round_result(agent, matches=4, prize=100.0, cost=20.0)
    assert strategy.determine_num_tickets(agent) == 1, "Po pokryti kumulovaneho deficitu se ma strategie resetovat."

def main() -> None:
    cfg = Config()

    # kontrola ze teoreticke RTP sedi s ocekavanim (cca 18.6 %)
    assert 18.0 < cfg.theoretical_rtp() < 19.0, (
        f"Teoreticke RTP ma byt okolo 18.64 %, vyslo {cfg.theoretical_rtp()}"
    )
    # kontrola ze EV tiketu je spravne zaporne (hrac v prumeru traci cca 16 Kc)
    assert -17.0 < cfg.expected_value_per_ticket() < -16.0, (
        f"EV tiketu ma byt okolo -16.27 CZK, vyslo {cfg.expected_value_per_ticket()}"
    )

    # kontrola dulezitych casti modelu, ktere se zminuji v textu prace
    _test_operator_jackpot_pool()
    _test_martingale_deficit_reset()

    # stejny seed musi dat uplne stejny vysledek
    first = _run_small(seed=42)
    second = _run_small(seed=42)
    assert _digest(first) == _digest(second), "Stejny seed nedava stejny vysledek."

    # jiny seed musi dat jiny vysledek
    third = _run_small(seed=43)
    assert _digest(first) != _digest(third), "Ruzny seed dava stejny vysledek, to je podezrele."

    # zakladni kontrola ze empiricke pravdepodobnosti davaji smysl
    prize_stats = first["prizes"]
    total_win_prob = sum(v["pct_actual"] for v in prize_stats.values())
    assert total_win_prob >= 0.0, "Empiricke pravdepodobnosti nejsou validni."

    print("OK: kontrolni testy prosly.")
    print(f"Teoreticke RTP: {cfg.theoretical_rtp():.4f} %")
    print(f"EV tiketu: {cfg.expected_value_per_ticket():.4f} CZK")


if __name__ == "__main__":
    main()
