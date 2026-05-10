# Simulace herních strategií v loterii 6/49

Tohle je praktická část mé bakalářky. Simuluju zjednodušenou loterii 6/49 pomocí agentního modelování a Monte Carlo metody. Různí agenti hrají podle různých strategií a já sleduju co se děje s jejich penězi a jak se daří provozovateli.

Není to kalibrace Sportky, spíš model kde zkouším jestli různé strategie (Martingale, HotCold, fixní čísla atd.) nějak ovlivňují výsledky, nebo jestli je to prostě jedno a všichni stejně tratí.

V základním běhu je populace rozdělená rovnoměrně mezi pět strategií. Při 100 agentech má každá strategie 20 hráčů: Nahodna, FixedCisla, Martingale, HotCold_hot a HotCold_cold.

## Co je potřeba

- Python 3.11 nebo novější
- `uv` - správce balíčků, dá se nainstalovat přes `pip install uv`

Pak stačí:

uv sync


## Jak to spustit

Jsou tam tři profily:
- `quick` - 100 běhů, rychlá kontrola jestli to vůbec funguje
- `thesis` - 1000 běhů, to co jde do práce (výchozí)
- `deep` - 10000 běhů, pro jistotu jestli se výsledky stabilizují

uv run main.py --profile quick
uv run main.py --profile thesis --scenarios
uv run main.py --profile deep

Jde to taky pustit s vlastním nastavením:


uv run main.py --simulations 50 --rounds 20 --agents 30


## Co program vypíše

Výsledky se ukládají do složky `output_thesis/` (nebo `output_quick/` podle profilu). Uvnitř jsou:

- `figures/` - grafy, hlavně distribuce ROI, kapitál provozovatele přes čas, pravděpodobnosti výher
- `csv/` - tabulky se shrnutím výsledků podle strategií a jednotlivých MC běhů
- `reference/` - srovnání s reálnými loteriemi (jen pro kontext, ne pro kalibraci)
- `metadata.json` - konfigurace běhu, abych věděl s čím byl výsledek vygenerován

Nejdůležitější CSV jsou `strategy_summary.csv` (průměrné ROI a míra bankrotu podle strategie) a `run_summary.csv` (výsledky po jednotlivých MC bězích).


## Kontrolní testy

uv run kontrolni_testy.py

Ověřují základní věci: jestli sedí kombinatorika pravděpodobností, jestli stejný seed dává stejné výsledky a jestli jiný seed dává jiné výsledky.
