from __future__ import annotations

# Soubor ridi Monte Carlo simulaci.
# V kazdem behu se resetuje loterie, provozovatel a hraci.

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
        # ulozime konfiguraci simulace
        self._config = config
        # ulozime seznam agentu, kteri budou hrat
        self._agents = agents
        # pokud neni predany sberac statistik, vytvorime novy
        self._stats = stats_collector or SberStatistik()
        # docasne PRNG - pred kazdym behem se stejne resetuji pres SeedSequence
        self._draw_prng = PRNG(0)
        self._ticket_prng = PRNG(1)
        # vytvorime loterii se samostatnym PRNG pro losovani a tikety
        self._lottery = Loterie(config, self._draw_prng, self._ticket_prng)
        # vytvorime provozovatele, ktery drzi kapital a jackpotovy fond
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
        # pocet behu vezmeme z konfigurace
        total = self._config.num_simulations
        # z jednoho seedu se vyrobi nezavisle sekvence pro kazdy beh
        master = npr.SeedSequence(self._config.seed)
        run_sequences = master.spawn(start_run_id + total)[start_run_id:]

        # postupne spustime vsechny MC behy
        for local_id, run_ss in enumerate(run_sequences):
            # skutecne cislo behu se muze posunout pomoci start_run_id
            run_id = start_run_id + local_id
            # spustime jeden konkretni beh simulace
            self._run_single(run_id, run_ss)

            if self._on_run_complete is not None:
                self._on_run_complete(local_id + 1, total)

        return self._stats

    def _run_single(self, run_id: int, run_ss: npr.SeedSequence) -> None:
        # kazdy beh ma svuj vlastni seed - losovani a tikety maji oddelene proudy
        draw_ss, ticket_ss = run_ss.spawn(2)
        self._draw_prng.reset(draw_ss)
        self._ticket_prng.reset(ticket_ss)
        # resetujeme stav loterie pred novym behem
        self._lottery.reset()
        # resetujeme stav provozovatele pred novym behem
        self._operator.reset()
        # resetujeme vsechny agenty na zacatek
        for agent in self._agents:
            agent.reset()

        # sem se budou ukladat souhrny jednotlivych kol
        round_data = []

        # hlavni cyklus pres kola v jednom behu
        for _ in range(self._config.num_rounds):
            # pocitadlo prodanych tiketu v kole
            round_tickets = 0
            # tady docasne drzime sazky pred losovanim
            pending_results = []
            # kazdy agent se rozhodne, jestli a kolik tiketu koupi
            for agent in self._agents:
                # agent pripravi tikety podle sve strategie
                pending = agent.place_bets(self._lottery)
                # pokud agent v kole hral, ulozime jeho sazku
                if pending is not None:
                    round_tickets += int(pending["tickets"])
                    pending_results.append((agent, pending))

            # nejdriv se vyberou sazky, az potom se losuje
            round_revenue = self._operator.collect_revenue(round_tickets)
            # loterie prevezme aktualni jackpot od provozovatele
            self._lottery.update_jackpot(self._operator.jackpot_pool)
            drawn = self._lottery.conduct_draw()

            # sem ulozime pocty shod za jednotlive tikety
            flat_ticket_matches = []
            # pocet jackpotovych tiketu v aktualnim kole
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

            # finalni vysledky agentu v danem kole
            agent_results = []
            # samostatny seznam jackpotovych udalosti pro export
            jackpot_events = []
            for agent, pending, matches_for_agent in flat_ticket_matches:
                prizes = []
                for ticket_idx, matches in enumerate(matches_for_agent):
                    # fixni vyhry zustanou fixni, jackpot bere podil
                    prize = self._lottery.prize_for_matches(matches, jackpot_share=jackpot_share)
                    prizes.append(prize)
                    if matches == self._config.draw_size:
                        # ulozime detail jackpotu pro pozdejsi kontrolu
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
                # agentovi pripiseme vyhru a ulozime vysledek kola
                result = agent.resolve_bets(pending, matches_for_agent, prizes)
                # vysledek jeste potrebuje projit pres vyplatu provozovatele
                agent_results.append((agent, result))

            # skutecne vyplacene castky v danem kole
            round_payouts_actual = 0.0
            # pomocna promenna, jestli v kole padl a byl vyplacen jackpot
            jackpot_paid = False
            for idx, (agent, result) in enumerate(agent_results):
                # celkova vyhra, kterou agent podle pravidel vyhral
                requested_prize = float(result.get("prize", 0.0))
                if requested_prize <= 0:
                    continue

                # rozdelit vyhru na fixni cast a jackpotovou cast
                fixed_requested = 0.0
                jackpot_requested = 0.0
                ticket_matches = result.get("ticket_matches", [])
                ticket_prizes = result.get("ticket_prizes", [])
                # projdeme vsechny tikety a rozdelime vyhry podle typu
                for matches, prize in zip(ticket_matches, ticket_prizes):
                    if matches == self._config.draw_size:
                        jackpot_requested += float(prize)
                    else:
                        fixed_requested += float(prize)

                # kolik se realne podarilo agentovi vyplatit
                paid_amount = 0.0
                if fixed_requested > 0:
                    # fixni vyhry se plati z kapitalu provozovatele
                    paid_fixed = self._operator.pay_prize(
                        fixed_requested,
                        current_round=self._lottery.current_round,
                        is_jackpot=False,
                    )
                    if not paid_fixed:
                        # castka, kterou uz provozovatel nedokazal zaplatit
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
                    # fixni vyhra byla uspesne vyplacena
                    paid_amount += fixed_requested

                if jackpot_requested > 0:
                    # jackpot se plati z oddeleneho fondu
                    paid_jackpot = self._operator.pay_prize(
                        jackpot_requested,
                        current_round=self._lottery.current_round,
                        is_jackpot=True,
                    )
                    if not paid_jackpot:
                        # zapocteme to, co se uz stihlo vyplatit
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
                    # jackpotova vyhra byla uspesne vyplacena
                    paid_amount += jackpot_requested
                    # poznamename, ze jackpot v kole opravdu probehl
                    jackpot_paid = True

                round_payouts_actual += paid_amount

            # po vyplatach dorovnat jackpot na minimum
            self._operator.top_up_jackpot_pool(current_round=self._lottery.current_round)
            # synchronizovat loterii s provozovatelem
            self._lottery.update_jackpot(self._operator.jackpot_pool)

            # provozovatel si ulozi trzby, vyplaty a kapital po kole
            self._operator.record_round(round_revenue, round_payouts_actual)

            # ulozime data kola pro statistiky a grafy
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

            # pokud provozovatel zkrachoval, dalsi kola uz nema smysl simulovat
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
