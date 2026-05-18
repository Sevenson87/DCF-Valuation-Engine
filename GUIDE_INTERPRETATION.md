# Guide d'interprétation — DCF Valuation Engine

## Ce que fait le projet
Modèle de valorisation par actualisation des flux de trésorerie (DCF). Télécharge automatiquement les données financières via yfinance, calcule le WACC (coût du capital) via CAPM, projette les FCF sur 5 ans selon 3 scénarios (Bear/Base/Bull), et compare la valeur intrinsèque au prix de marché pour calculer la marge de sécurité.

---

## Output généré
`DCF_Report_TICKER.html` — rapport interactif avec tous les calculs détaillés.

---

## Comment lire le rapport HTML

### Section 1 — WACC et coût du capital
| Paramètre | Ce que c'est |
|-----------|-------------|
| Ke (coût des fonds propres) | = Rf + β × (Rm - Rf) via CAPM |
| Kd (coût de la dette) | = taux d'intérêt × (1 - taux d'imposition) |
| WACC | = Ke × (E/V) + Kd × (D/V) — taux d'actualisation |

- **WACC élevé (> 12%)** → entreprise risquée ou endettée → flux futurs pèsent moins → valeur intrinsèque plus basse
- **Bêta > 1.5** → très volatile, Ke sera élevé (ex : NVDA β ≈ 1.7)

### Section 2 — Tableau des scénarios DCF
| Scénario | Taux de croissance | Usage |
|---------|-------------------|-------|
| Bear | Croissance faible / stagnation | Pire cas, valeur plancher |
| Base | Tendance historique récente | Estimation centrale |
| Bull | Accélération de la croissance | Meilleur cas, upside potentiel |

**Comment lire la valeur intrinsèque :**
- Si prix marché > valeur intrinsèque Bull → **surévalué dans tous les scénarios** (ex : NVDA $198 vs Bull $144)
- Si prix marché < valeur intrinsèque Bear → **sous-évalué même dans le pire cas**
- La zone entre Bear et Bull = **fourchette de juste valeur**

### Section 3 — Marge de Sécurité (Margin of Safety)
```
MoS = (Valeur intrinsèque - Prix marché) / Valeur intrinsèque × 100
```
- **MoS > +30%** → achat avec marge confortable (sous-évalué)
- **MoS entre -10% et +10%** → à peu près correctement valorisé
- **MoS < -50%** → fortement surévalué (attention aux growth stocks)

> Exemple : NVDA à $198 avec valeur base $106 → MoS = -87% → le marché paye une prime de croissance future très agressive. Ce n'est pas nécessairement une erreur, mais le DCF quantifie ce que le marché intègre.

### Section 4 — Matrice de sensibilité
- Lignes = variation du taux de croissance (-2% à +2% autour du base)
- Colonnes = variation du WACC (-1% à +1%)
- Chaque case = valeur intrinsèque résultante
- **Utilisée pour voir la robustesse de la valorisation** : si la valeur reste au-dessus du prix dans la majorité des cases → thèse solide

### Section 5 — Multiples de marché (P/E, EV/EBITDA, P/FCF)
- Compare les multiples actuels aux médianes sectorielles
- Complète le DCF qui est une approche absolue (le DCF + les multiples = validation croisée)

---

## Signaux d'alerte
- **WACC non calculable** → dette nulle (rare) ou données manquantes → vérifier le ticker
- **Croissance capée à 40%** → le modèle plafonne les CAGR extrêmes pour éviter les valorisations infinies
- **FCF négatif** → le modèle bascule sur les revenus ou les bénéfices → moins fiable, traiter avec précaution
- **Reverse DCF affiché** → montre le taux de croissance que le marché intègre implicitement dans le prix actuel
