# Guide de lancement — DCF Valuation Model

## Prérequis

- Python 3.8+
- Connexion internet (données financières via Yahoo Finance)

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

### Mode interactif (saisie du ticker au clavier)
```bash
python dcf_advanced.py
```
Le programme te demande le ticker, puis les paramètres optionnels (taux terminal, horizon).

### Mode direct (un seul ticker)
```bash
python dcf_advanced.py AAPL
python dcf_advanced.py NVDA
python dcf_advanced.py MSFT
```

### Mode batch (plusieurs tickers d'un coup)
```bash
python dcf_advanced.py AAPL NVDA MSFT GOOGL
```
Un rapport HTML est généré pour chaque ticker.

## Résultat

Un fichier `DCF_Report_TICKER.html` est créé dans le même dossier.
Ouvre-le directement dans Chrome — aucune installation supplémentaire nécessaire.

## Tickers compatibles

Tout ticker disponible sur Yahoo Finance avec des **états financiers publics** :
- Actions US : `AAPL`, `NVDA`, `MSFT`, `GOOGL`, `AMZN`, `META`...
- Actions canadiennes : `RY.TO`, `TD.TO`, `CNR.TO`...
- Actions européennes : `ASML`, `LVMH.PA`...

**Non compatibles** : ETFs, indices, cryptos (pas d'états financiers).

## Paramètres modifiables

En haut de `dcf_advanced.py` :

```python
RISK_FREE_RATE = 0.045        # Taux sans risque (10Y Treasury)
MARKET_RISK_PREMIUM = 0.055   # Prime de risque marché
DEFAULT_TERMINAL_GROWTH = 0.025  # Croissance terminale
DEFAULT_PROJECTION_YEARS = 5     # Horizon de projection
```

## Ce que le rapport contient

- **Recommandation** (Strong Buy → Strong Sell) basée sur le cas de base
- **Valeur intrinsèque** Bear / Base / Bull
- **WACC détaillé** (coût equity CAPM, coût dette, pondérations)
- **Bridge EV → Equity** (EV → dette nette → valeur par action)
- **Graphique FCF projeté** (SVG intégré)
- **FCF historique** (4 dernières années)
- **Matrice de sensibilité** (valeur selon WACC × taux de croissance)
- **Hypothèses clés**

## Problèmes fréquents

**`[ERROR] Invalid ticker`** → Vérifie l'orthographe. Les tickers canadiens ont `.TO` (ex: `RY.TO`).

**`No cash flow data`** → Le ticker est un ETF ou n'a pas d'états financiers publics.

**`ModuleNotFoundError`** → Lance `pip install -r requirements.txt`.

**Valeur aberrante** → Le DCF est sensible à la croissance terminale. Si le FCF historique est négatif ou très volatile, les résultats seront instables — c'est normal.
