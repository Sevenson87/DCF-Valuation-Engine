# DCF Valuation Model

> Fundamental intrinsic value analysis via Discounted Cash Flow — multi-scenario, WACC auto-computed, HTML report.

**FR** | [EN below](#dcf-valuation-model-en)

---

## Modèle de valorisation DCF

Calcule la valeur intrinsèque d'une action via un modèle DCF (Discounted Cash Flow) institutionnel. Télécharge automatiquement les données financières via yfinance et génère un rapport HTML self-contained.

### Fonctionnalités

- **WACC automatique** via le modèle CAPM (bêta, prime de risque marché, taux sans risque temps réel)
- **3 scénarios** Bear / Base / Bull avec hypothèses de croissance différenciées
- **Marge de sécurité** (Benjamin Graham) : `(IV − Prix) / IV × 100`
- **Matrice de sensibilité** WACC × taux de croissance terminal
- **Rapport HTML** self-contained (~26KB) avec visualisation des scénarios
- **Multiples de marché** : P/E, EV/EBITDA, P/FCF, P/Book

### Usage

```bash
pip install -r requirements.txt

# Analyse interactive (mode questions-réponses)
python dcf_advanced.py

# Analyse directe
python dcf_advanced.py AAPL
python dcf_advanced.py NVDA

# Mode batch (plusieurs tickers)
python dcf_advanced.py AAPL NVDA MSFT
```

### Exemple de résultats

| Ticker | Prix marché | Bear | Base | Bull | Marge de sécurité |
|--------|-------------|------|------|------|-------------------|
| AAPL   | $276.83     | $82  | $87  | $92  | −217% (survalué)  |
| NVDA   | $198.48     | $62  | $106 | $144 | −87% (survalué)   |

### Méthodologie

```
FCF projeté(t) = FCF₀ × (1 + g)^t
Valeur terminale = FCF_n × (1 + g_terminal) / (WACC − g_terminal)
VPT = Σ FCF(t) / (1 + WACC)^t + TV / (1 + WACC)^n
```

Le WACC est calculé via CAPM : `Ke = Rf + β × (Rm − Rf)`, où Rf = rendement du T-Bill 10Y et β provient de yfinance.

### Fichiers

| Fichier | Description |
|---------|-------------|
| `dcf_advanced.py` | Script principal (1 800 lignes) |
| `requirements.txt` | Dépendances Python |
| `LANCEMENT.md` | Guide de démarrage détaillé |
| `DCF_Report_AAPL.html` | Exemple de rapport généré |
| `DCF_Report_NVDA.html` | Exemple de rapport généré |

---

## DCF Valuation Model (EN)

Computes intrinsic stock value via institutional DCF analysis. Auto-downloads financial data via yfinance and generates a self-contained HTML report.

### Features

- **Automatic WACC** via CAPM model (beta, market risk premium, real-time risk-free rate)
- **3 scenarios** Bear / Base / Bull with differentiated growth assumptions
- **Margin of Safety** (Benjamin Graham): `(IV − Price) / IV × 100`
- **Sensitivity matrix** WACC × terminal growth rate
- **Self-contained HTML report** (~26KB) with scenario visualization
- **Market multiples**: P/E, EV/EBITDA, P/FCF, P/Book

### Usage

```bash
pip install -r requirements.txt
python dcf_advanced.py AAPL           # Direct analysis
python dcf_advanced.py AAPL NVDA MSFT # Batch mode
```

### Methodology

| Component | Formula |
|-----------|---------|
| WACC | `(E/V) × Ke + (D/V) × Kd × (1−T)` |
| Cost of equity (CAPM) | `Ke = Rf + β × (Rm − Rf)` |
| FCF projection | `FCF₀ × (1 + g)^t` |
| Terminal Value | `FCF_n × (1 + g_t) / (WACC − g_t)` |
| Margin of Safety | `(IV − Price) / IV × 100` |

### Limitations

- Model assumes stable FCF growth; inappropriate for pre-revenue or highly cyclical companies
- WACC components sourced from yfinance — verify manually for precision work
- Terminal growth rate is the most sensitive assumption: ±1% changes fair value by 20–40%

---

*Built with Python 3.8+ · yfinance · pandas · numpy*
