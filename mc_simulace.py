from __future__ import annotations

from typing import Callable, List, Optional

import numpy.random as npr

from base import Agent
from config import Config
from loterie import Loterie
from prng import PRNG
from provozovatel import Provozovatel
from statistiky import SberStatistik


# hlavni trida co ridi cele monte carlo
# opakuje jednotlive behy, v kazdem resetuje agenty a loterii
class MCSimulace:

    def __init__(
        self,
        config: Config,
        agents: List[Agent],
        stats_collector: Optional[SberStatistik] = None,
    ) -> None:
        self._config = config
        self._agents = agents
        self._stats = stats_collector or SberStatistik()
        # docasne PRNG - pred kazdym behem se stejne resetuji pres SeedSequence
        self._draw_prng = PRNG(0)
        self._ticket_prng = PRNG(1)
        self._lottery = Loterie(config, self._draw_prng, self._ticket_prng)
        self._operator = Provozovatel(config)
        self._on_run_complete: Optional[Callable[[int, int], None]] = None

    @property
    def statistics(self) -> SberStatistik:
        return self._stats

    @property
    def lottery(self) -> Loterie:
        return self._lottery

    @property
    def operator(self) -> Provozovatel:
        return self._operator

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        self._on_run_complete = callback

    def run(self, start_run_id: int = 0) -> SberStatistik:
        total = self._config.num_simulations
        # z jednoho seedu se vyrobi nezavisle sekvence pro kazdy beh
        master = npr.SeedSequence(self._config.seed)
        run_sequences = master.spawn(start_run_id + total)[start_run_id:]

        for local_id, run_ss in enumerate(run_sequences):
            run_id = start_run_id + local_id
            self._run_single(run_id, run_ss)

            if self._on_run_complete is not None:
                self._on_run_complete(local_id + 1, total)

        return self._stats

    def _run_single(self, run_id: int, run_ss: npr.SeedSequence) -> None:
        # kazdy beh ma svuj vlastni seed - losovani a tikety maji oddelene proudy
        draw_ss, ticket_ss = run_ss.spawn(2)
        self._draw_prng.reset(draw_ss)
        self._ticket_prng.reset(ticket_ss)
        self._lottery.reset()
        self._operator.reset()
        for agent in self._agents:
            agent.reset()

        round_data = []

        for _ in range(self._config.num_rounds):
            round_tickets = 0
            pending_results = []
            for agent in self._agents:
                pending = agent.place_bets(self._lottery)
                if pending is not None:
                    round_tickets += int(pending["tickets"])
                    pending_results.append((agent, pending))

            # nejdriv se vyberou sazky, az potom se losuje
            round_revenue = self._operator.collect_revenue(round_tickets)
            # loterie prevezme aktualni jackpot od provozovatele
            self._lottery.update_jackpot(self._operator.jackpot_pool)
            drawn = self._lottery.conduct_draw()

            flat_ticket_matches = []
            jackpot_winners = 0
            for agent, pending in pending_results:
                matches_for_agent = []
                for numbers in pending.get("ticket_numbers", []):
                    # kolik cisel trefil na jednom tiketu
                    matches = self._lottery.count_matches(numbers)
                    matches_for_agent.append(matches)
                    if matches == self._config.draw_size:
                        jackpot_winners += 1
                flat_ticket_matches.append((agent, pending, matches_for_agent))

            # vic vyhercich jackpotu ve stejnem kole = deli se
            jackpot_share = self._operator.jackpot_pool / jackpot_winners if jackpot_winners else None

            agent_results = []
            jackpot_events = []
            for agent, pending, matches_for_agent in flat_ticket_matches:
                prizes = []
                for ticket_idx, matches in enumerate(matches_for_agent):
                    # fixni vyhry zustanou fixni, jackpot bere podil
                    prize = self._lottery.prize_for_matches(matches, jackpot_share=jackpot_share)
                    prizes.append(prize)
                    if matches == self._config.draw_size:
                        jackpot_events.append({
                            "run_id": run_id,
                            "round": self._lottery.current_round,
                            "agent_id": agent.id,
                            "strategy": agent.strategy.name,
                            "ticket_index": ticket_idx,
                            "ticket_numbers": " ".join(map(str, pending.get("ticket_numbers", [])[ticket_idx])),
                            "drawn_numbers": " ".join(map(str, drawn)),
                            "jackpot_share": jackpot_share or 0.0,
                            "jackpot_winners_in_round": jackpot_winners,
                        })
                result = agent.resolve_bets(pending, matches_for_agent, prizes)
                agent_results.append((agent, result))

            round_payouts_actual = 0.0
            jackpot_paid = False
            for idx, (agent, result) in enumerate(agent_results):
                requested_prize = float(result.get("prize", 0.0))
                if requested_prize <= 0:
                    continue

                # rozdelit vyhru na fixni cast a jackpotovou cast
                fixed_requested = 0.0
                jackpot_requested = 0.0
                ticket_matches = result.get("ticket_matches", [])
                ticket_prizes = result.get("ticket_prizes", [])
                for matches, prize in zip(ticket_matches, ticket_prizes):
                    if matches == self._config.draw_size:
                        jackpot_requested += float(prize)
                    else:
                        fixed_requested += float(prize)

                paid_amount = 0.0
                if fixed_requested > 0:
                    # fixni vyhry se plati z kapitalu provozovatele
                    paid_fixed = self._operator.pay_prize(
                        fixed_requested,
                        current_round=self._lottery.current_round,
                        is_jackpot=False,
                    )
                    if not paid_fixed:
                        unpaid_amount = requested_prize - paid_amount
                        extra_unregistered = max(0.0, unpaid_amount - fixed_requested)
                        if extra_unregistered > 0:
                            self._operator.register_unpaid_prize(
                                extra_unregistered,
                                current_round=self._lottery.current_round,
                            )
                        agent.revoke_unpaid_prize(unpaid_amount)
                        # provozovatel zkrachoval - zbytek hracu taky nedostane nic
                        for remaining_agent, remaining_result in agent_results[idx + 1:]:
                            remaining_prize = float(remaining_result.get("prize", 0.0))
                            if remaining_prize > 0:
                                remaining_agent.revoke_unpaid_prize(remaining_prize)
                                self._operator.register_unpaid_prize(
                                    remaining_prize,
                                    current_round=self._lottery.current_round,
                                )
                        break
                    paid_amount += fixed_requested

                if jackpot_requested > 0:
                    # jackpot se plati z oddeleneho fondu
                    paid_jackpot = self._operator.pay_prize(
                        jackpot_requested,
                        current_round=self._lottery.current_round,
                        is_jackpot=True,
                    )
                    if not paid_jackpot:
                        round_payouts_actual += paid_amount
                        unpaid_amount = requested_prize - paid_amount
                        extra_unregistered = max(0.0, unpaid_amount - jackpot_requested)
                        if extra_unregistered > 0:
                            self._operator.register_unpaid_prize(
                                extra_unregistered,
                                current_round=self._lottery.current_round,
                            )
                        agent.revoke_unpaid_prize(unpaid_amount)
                        for remaining_agent, remaining_result in agent_results[idx + 1:]:
                            remaining_prize = float(remaining_result.get("prize", 0.0))
                            if remaining_prize > 0:
                                remaining_agent.revoke_unpaid_prize(remaining_prize)
                                self._operator.register_unpaid_prize(
                                    remaining_prize,
                                    current_round=self._lottery.current_round,
                                )
                        break
                    paid_amount += jackpot_requested
                    jackpot_paid = True

                round_payouts_actual += paid_amount

            # po vyplatach dorovnat jackpot na minimum
            self._operator.top_up_jackpot_pool(current_round=self._lottery.current_round)
            # synchronizovat loterii s provozovatelem
            self._lottery.update_jackpot(self._operator.jackpot_pool)

            self._operator.record_round(round_revenue, round_payouts_actual)

            round_data.append({
                "round": self._lottery.current_round,
                "drawn": drawn,
                "tickets_sold": round_tickets,
                "revenue": round_revenue,
                "payouts": round_payouts_actual,
                "operator_capital": self._operator.capital,
                "active_agents": len(pending_results),
                "bankrupt": self._operator.is_bankrupt,
                "jackpot_winners": jackpot_winners,
                "jackpot_events": jackpot_events,
            })

            # frekvence se updatuji az po vyhodnoceni, aby hotcold nevidel tohle kolo
            self._lottery.commit_draw_frequencies()

            if self._operator.is_bankrupt:
                break

        # ulozit vysledky behu do sberace statistik
        self._stats.record_run(
            run_id=run_id,
            operator_summary=self._operator.get_summary(),
            agent_summaries=[a.get_summary() for a in self._agents],
            round_data=round_data,
        )

    def __repr__(self) -> str:
        return (
            f"MCSimulace(runs={self._config.num_simulations}, "
            f"rounds_per_run={self._config.num_rounds}, agents={len(self._agents)})"
        )
