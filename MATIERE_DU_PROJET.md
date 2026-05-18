# Matière du Projet 02 — DCF Valuation Engine

## Vue d'ensemble

Ce projet implémente un modèle d'évaluation par Discounted Cash Flow (DCF) complet :
WACC automatique via CAPM, projections 5 ans, valeur terminale Gordon Growth,
analyse de scénarios Bear/Base/Bull, matrice de sensibilité, et reverse DCF.

---

## 1. WACC — Coût Moyen Pondéré du Capital

Le WACC est le taux d'actualisation qui reflète le risque global du financement :

```
WACC = (E/V) × Ke + (D/V) × Kd × (1 − Tc)
```

| Variable | Signification | Source |
|----------|--------------|--------|
| `E` | Valeur de marché des capitaux propres (Market Cap) | yfinance |
| `D` | Valeur de marché de la dette | yfinance (totalDebt) |
| `V` | E + D | Calculé |
| `Ke` | Coût des capitaux propres (CAPM) | Voir ci-dessous |
| `Kd` | Coût de la dette = Intérêts / Dette totale | yfinance |
| `Tc` | Taux d'imposition effectif | yfinance |

### Coût des capitaux propres — CAPM

```
Ke = Rf + β × (Rm − Rf)
```

- `Rf` = 4.5% (taux sans risque, T-Bills 10 ans US)
- `β` = Beta de l'action vs S&P 500
- `Rm − Rf` = 5.5% (prime de risque historique actions US)

**Exemple META** : β ≈ 1.2 → Ke = 4.5% + 1.2 × 5.5% = 11.1%

---

## 2. Modèle DCF

### 2.1 Projection des Free Cash Flows

```
FCF_t = FCF_0 × (1 + g)^t   pour t = 1 à N
```

Le taux de croissance `g` est estimé dans cet ordre de priorité :
1. **CAGR historique FCF** (si disponible et < 40%)
2. **Proxy croissance des bénéfices** (EPS CAGR)
3. **Proxy croissance du chiffre d'affaires**
4. **Défaut** : 8% (large cap) / 5% (petite cap)

**Cap à 40%** : `g = min(max(g, 0.03), 0.40)`. Aucune entreprise ne peut croître
à 40%+ indéfiniment sans dépasser la taille de l'économie mondiale.

### 2.2 Valeur terminale (Gordon Growth)

```
TV = FCF_N × (1 + g_terminal) / (WACC − g_terminal)
```

- `g_terminal` = 2.5% (croissance perpétuelle ≈ croissance du PIB)
- `TV` représente souvent 60–80% de la valeur intrinsèque → **très sensible au WACC**

### 2.3 Actualisation

```
PV_FCF = Σ FCF_t / (1 + WACC)^t
PV_TV  = TV / (1 + WACC)^N

Enterprise Value = PV_FCF + PV_TV
Equity Value     = EV − Dette nette
Fair Value / sh. = Equity Value / Shares Outstanding
```

---

## 3. Marge de sécurité (Benjamin Graham)

```
MoS = (Valeur intrinsèque − Prix de marché) / Valeur intrinsèque × 100
```

- **MoS > 20%** : entrée conservatrice (le stock peut chuter de 20% et tu es toujours
  au seuil de rentabilité selon ton modèle)
- **MoS < 0%** : marché paye plus que la valeur intrinsèque → croissance parfaite
  déjà intégrée dans le prix
- **Point de non-retour** : quand le WACC augmente (taux directeurs en hausse), la
  valeur terminale s'effondre et le MoS négatif s'accroît fortement

**MoS faible sur META** → le marché a déjà pricé une croissance forte. Si les taux
montent de 100bps, le WACC passe de 11% à 12% → la valeur chute de ~20%.

---

## 4. Analyse de scénarios

| Scénario | Croissance | Logique |
|----------|-----------|---------|
| **Bear** | Base × 0.70 | Ralentissement structurel, concurrence accrue |
| **Base** | Estimée | Continuation de la trajectoire actuelle |
| **Bull** | Base × 1.30 | Exécution parfaite, expansion de marché |

---

## 5. Reverse DCF — Croissance implicite du marché

**Question inverse** : à quel taux de croissance faut-il croire pour justifier le prix actuel ?

```
Prix = Σ FCF_0×(1+g_impl)^t/(1+WACC)^t + TV(g_impl)/(1+WACC)^N
```

On résout numériquement pour `g_impl` (dichotomie sur [0%, 60%]).

- `g_impl > g_modèle` → le marché anticipe plus que ton modèle (stock cher)
- `g_impl < g_modèle` → ton modèle est plus optimiste (stock sous-évalué selon toi)

---

## 6. Matrice de sensibilité

La matrice croise deux axes :
- **Axe X** : WACC (±200bps autour du WACC base)
- **Axe Y** : Taux de croissance (±5 pts autour du base)

Chaque cellule montre la fair value / share. Les cellules vertes = sous le prix actuel
(sous-évalué), rouges = au-dessus (surévalué).

**Utilité** : identifier la zone "marge de sécurité" — quelle combinaison
WACC × croissance préserve encore une valeur > prix de marché.

---

## 7. Multiples de valorisation (contexte de marché)

| Multiple | Formule | Ce qu'il mesure |
|----------|---------|----------------|
| **P/E trailing** | Prix / BPA dernière année | Cherté relative aux bénéfices actuels |
| **P/E forward** | Prix / BPA estimé N+1 | Cherté aux bénéfices anticipés |
| **EV/EBITDA** | (Market Cap + Dette − Cash) / EBITDA | Cherté opérationnelle (neutral au levier) |
| **P/Book** | Prix / Valeur comptable / action | Premium sur les actifs nets |
| **Market Cap / FCF** | Market Cap / Free Cash Flow | Price-to-FCF (équivalent P/E pour les cash generators) |

Ces multiples ne remplacent pas le DCF : ils donnent un contexte relatif (vs secteur, vs historique).

---

## 8. Limites du modèle

1. **Erreur d'estimation du WACC** : une erreur de ±1% sur le WACC peut changer la valeur de ±20–30%
2. **Qualité du FCF projeté** : si le FCF historique est négatif ou erratique, la projection perd de sens
3. **Valeur terminale dominante** : 70–80% de la valeur vient de la TV → hypersensible à `g_terminal`
4. **Pas de dividendes** : le modèle ne tient pas compte des dividendes explicitement
5. **Données yfinance** : parfois imprécises pour les grandes capitalisations

---

## 9. Exemples de résultats (2026-05-04)

| Ticker | Prix | DCF Bear | DCF Base | DCF Bull | Croissance base |
|--------|------|----------|----------|----------|-----------------|
| AAPL | $276 | $82 | $87 | $92 | 3% (FCF plat) |
| NVDA | $198 | $62 | $106 | $144 | 40% (cap CAGR) |

NVDA à 40% de croissance : le marché paye une prime de ~87% au-dessus de la valeur DCF → croissance parfaite déjà intégrée.

---

## 10. Glossaire

| Terme | Définition |
|-------|-----------|
| **FCF (Free Cash Flow)** | OCF − CapEx : cash réellement généré après investissements |
| **WACC** | Taux d'actualisation = coût moyen de financement (dette + capitaux propres) |
| **Enterprise Value** | Valeur totale de l'entreprise (dette + équité − cash) |
| **Beta** | Sensibilité du titre au marché (β=1 → se comporte comme le marché) |
| **Gordon Growth** | Modèle de rente perpétuelle croissante : V = FCF / (r − g) |
| **Reverse DCF** | Calcul du taux de croissance implicite dans le prix actuel |
| **Marge de sécurité** | Coussin entre valeur intrinsèque et prix payé (concept Graham) |
