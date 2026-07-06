# Anthropic System Cards — registre & état d'intégration

But : incorporer les données **coût + qualité par effort** des System Cards Anthropic dans `raw-data.csv`,
puis `python3 gen/build.py`. Les grilles coût et qualité sont **couple-atomiques** (ratios à tâche
identique → graphe de liaison → consolidation, ancre `opus-4.8@medium = 1.0`). On ne compare **jamais**
des valeurs brutes entre benchmarks — uniquement des **ratios au sein d'un même benchmark**.

## Liste EXHAUSTIVE des System Cards (source : anthropic.com/system-cards, juillet 2026)

| Modèle | Date | Pages | PDF direct | Priorité | État |
|---|---|---|---|---|---|
| **Sonnet 5** | 2026-06-30 | 145 | https://www-cdn.anthropic.com/9e6a1044980d8c4ed85669faf9c2a8342e2e9f1e/Claude%20Sonnet%205%20System%20Card.pdf | — | ✅ **INTÉGRÉ** |
| **Fable 5 & Mythos 5** | 2026-06-30 | 319 | https://www-cdn.anthropic.com/d00db56fa754a1b115b6dd7cb2e3c342ee809620.pdf | ★★★ (sweeps Fable) | ⏳ à faire |
| **Opus 4.8** | 2026-05-28 | 246 | https://www-cdn.anthropic.com/0f0c97ad20d8005706296bd92aa1c27c6b2f4f61/Claude%20Opus%204.8%20System%20Card.pdf (alt hash: 0b4915911bb0d19eca5b5ee635c80fef830a37ea.pdf) | ★★★ (sweeps Opus 4.8/4.7 → comble opus-4.7@medium) | ✅ **INTÉGRÉ** |
| **Opus 4.7** | 2026-04-16 | 232 | https://www-cdn.anthropic.com/037f06850df7fbe871e206dad004c3db5fd50340/Claude%20Opus%204.7%20System%20Card.pdf | ★★ | ⏳ à faire |
| **Sonnet 4.6** | 2026-02-17 | ? | https://www-cdn.anthropic.com/78073f739564e986ff3e28522761a7a0b4484f84.pdf | ★★ | ⏳ à faire |
| **Opus 4.6** | 2026-02 | ? | https://www-cdn.anthropic.com/14e4fb01875d2a69f646fa5e574dea2b1c0ff7b5.pdf (alt: 0dd865075ad3132672ee0ab40b05a53f14cf5288.pdf, 6a5fa276ac68b9aeb0c8b6af5fa36326e0e166dd.pdf) | ★ (legacy) | ⏳ |
| **Mythos Preview** | 2026-04 | ? | page: anthropic.com/claude-mythos-preview-system-card | ☆ (config recherche) | ⏳ |
| Opus 4.5 | 2025-11 | ? | https://www-cdn.anthropic.com/bf10f64990cfda0ba858290be7b8cc6317685f47.pdf | ☆ legacy | — |
| Haiku 4.5 | 2025-10 | ? | https://www-cdn.anthropic.com/7aad69bf12627d42234e01ee7c36305dc2f6a970.pdf | ★ (Haiku, mais pas d'effort discret) | ⏳ |
| Sonnet 4.5 | 2025-09 | ? | https://www-cdn.anthropic.com/963373e433e489a87a10c823c52a0a013e9172dd.pdf | ☆ legacy | — |
| Opus 4.1 | 2025-08 | ? | https://www-cdn.anthropic.com/9fa30625273bafdf5af82c93719d7ca606485a16.pdf | ☆ legacy | — |
| Sonnet 4 & Opus 4 | 2025-05 | ? | https://www-cdn.anthropic.com/07b2a3f9902ee19fe39a36ca638e5ae987bc64dd.pdf (alt 6be99a52..., 4263b940...) | ☆ legacy | — |
| Sonnet 3.7 | 2025-02 | ? | https://www-cdn.anthropic.com/9ff93dfa8f445c932415d335c88852ef47f1201e.pdf | ☆ legacy | — |
| Haiku 3.5 & Sonnet 3.5 | 2024-10 | ? | https://www-cdn.anthropic.com/c7822cdc35ad788ec87e14b3a9d45010f1f86c38.pdf | ☆ trop vieux | — |
| Claude 3 | 2024-03 | ? | https://www-cdn.anthropic.com/c6a80a657af445f40e31afac050f3bf76d3b1404.pdf | ☆ | — |
| Claude 2 | 2023-07 | ? | https://www-cdn.anthropic.com/bd2a28d2535bfb0494cc8e2a3bf135d2e7523226/Model-Card-Claude-2.pdf | ☆ | — |

Modèles courants de la grille : Fable 5, Opus 4.8, Opus 4.7, Sonnet 5, Sonnet 4.6, Haiku 4.5.
→ cards prioritaires restantes : **Fable5/Mythos5**, **Opus 4.8**, **Opus 4.7**, **Sonnet 4.6**, **Haiku 4.5**.

## Méthode de traitement d'un PDF (les données riches sont dans les FIGURES = images)

`pdftoppm`/`pdftotext`/`pip` indisponibles dans l'env. Recette qui marche (scratchpad) :
```bash
cd <scratchpad>
curl -sL --max-time 120 -o card.pdf "<PDF_URL>"
uv pip install --target ./pylib pypdf pillow      # installe en local (system-site interdit)
# texte par page :
PYTHONPATH=./pylib python3 -c "import pypdf;r=pypdf.PdfReader('card.pdf');print(r.pages[N-1].extract_text())"
# extraire les figures (images embarquées) d'une plage de pages :
PYTHONPATH=./pylib python3 -c "import pypdf;r=pypdf.PdfReader('card.pdf');
[im.image.save(f'img/p{p+1}_{k}.png') for p in range(A,B) for k,im in enumerate(r.pages[p].images) if len(im.data)>15000]"
```
Puis **lire les PNG** avec l'outil Read (vision) et **digitaliser** les points (axe coût = log, à lire à ±10-15 %).
Le texte donne les tableaux récap (scores @max) ; les **figures effort×coût** donnent les sweeps complets.

## ✅ Sonnet 5 System Card — DÉJÀ INTÉGRÉ (source=`anthropic-syscard`)

Config (p115) : résultats Sonnet 5 = adaptive thinking **@max**, moyenne 5 essais (sauf exceptions notées).
Données ajoutées à `raw-data.csv` :
- **Scores qualité @max** (Table 8.1.A p114 + image de lancement pour Opus 4.8) — groupes :
  `scswebenchpro` (SWE-bench Pro 63.2/58.1/69.2), `schle-nt` (HLE no-tools 43.2/34.6/49.8),
  `scgdpval` (GDPval-AA v2 Elo 1618/1395/1615), `schealthbench` (57.8/44.2),
  + `automationbench` sonnet-5@max=13.5 ajouté au groupe existant. (modèles S5/S4.6/Opus4.8)
- **2 sweeps effort COMPLETS coût+qualité digitalisés des figures** (confound `digitized-logx`) :
  - `scfrontiercode` (fig 8.4.A p117) — Fable5, Opus4.8, Sonnet5 (low→max) + Sonnet4.6 (med/high/max).
    Scores : Fable 37.3/41.1/42.9/46.3/44.7 ; Opus4.8 25.3/26.9/30.3/34.3/31.3 ;
    Sonnet5 18.1/26.6/28.9/34.0/38.8 ; Sonnet4.6 med13.6/high15.1/max13.2.
  - `schletools` (fig 8.9.1.B p122, HLE with tools) — Sonnet5, Opus4.8, Sonnet4.6 (low→max).
    Sonnet5 36.5/47.2/52.8/54.6/57.4 ; Opus4.8 50.2/55.2/55.7/57.6/58.0 ; Sonnet4.6 34.9/46.5/49.7/(max)46.8.
  (coûts $/tâche digitalisés des axes log — voir les lignes `anthropic-syscard` dans raw-data.csv)
- Résultat : cost ratio-points 82 → **119**. Courbes qualité monotones SAUF **Sonnet 4.6 @max** qui
  redescend (U-inversé RÉEL : FrontierCode 15.1→13.2, HLE 49.7→46.8 — l'over-thinking dégrade). NE PAS corriger.

### Figures du Sonnet 5 card NON encore digitalisées (à faire si besoin, surtout qualité) :
p118 CursorBench (déjà couvert par notre source cursorbench), p123 BrowseComp scaling,
p124-132 multimodal (GDP.pdf, OSWorld, ChartMuseum, CharXiv, BenchCAD), p133 GDPval par effort,
p135/137 ?, p138-139 MMLU multilingue (GMMLU/INCLUDE/MILU). **Modèle « Mythos 5 »** apparaît (HLE :
low59.8/med62.6/high63.4/xhigh64.2/max64.7) = config recherche de Fable, **hors grille courante** → ignorer.

## ✅ Opus 4.8 System Card — INTÉGRÉ (2026-07-06, source=`anthropic-syscard`, ref `anthropic-opus48-syscard-pNNN`)

246 pages. **3 figures effort×coût digitalisées** (balayage low→max, axe log), chacune en groupe DÉDIÉ
(ratios 100 % intra-figure ; prix par tier Opus $0.06/Ktok, Sonnet $0.012/Ktok = ratio 5:1) :
- **`scsweproeff`** (fig 8.2.A p196, SWE-Bench Pro, tokens de sortie) — Opus 4.8 & Opus 4.7 low→max.
  Opus4.8 scores 63.6/66.0/67.4/69.7/69.3 ; Opus4.7 57.3/59.5/62.4/62.8/63.6. (Opus 4.6 legacy ignoré.)
- **`schleeff`** (fig 8.10.1.B p203, HLE avec outils, tokens TOTAUX) — Opus4.7 43.0/48.4/53.2/55.4/54.7 ;
  Opus4.8 50.2/55.2/55.7/57.6/57.9. (≈ identique au `schletools` du Sonnet5 card → confirme la même expérience.)
- **`scosweff`** (fig 8.12.6.B p222, OSWorld, tokens de sortie) — Opus4.8 78.5/80.0/81.4/83.1/83.4 ;
  **Opus4.7 73.8/75.7/79.8/80.2/82.8** (absent du groupe `osworld`/AA) ; Sonnet4.6 71.3/75.9/77.8/(max)78.4.
- Table 8.1.A p194-195 (scores @max Opus4.8 vs Opus4.7) et barres p205/p223 (DeepSearchQA, OfficeQA/Pro,
  Finance, MCP-Atlas) lues mais NON ajoutées (score-only @max, gain marginal vs les 3 sweeps).
- **Résultat** : `opus-4.7@medium` orange→**jaune** (anthropic-syscard + cursorbench) ; ladders coût+qualité
  Opus4.7 monotones sur 3 benchmarks. Corroboration globale **vert 24 · jaune 1 · orange 0 · rouge 0** (25 nœuds).
  cost-pts 119→142. Le seul jaune (`opus-4.7@medium`) passera vert avec la card Opus 4.7 propre.

## À FAIRE (ordre de priorité)
1. **Fable 5 & Mythos 5 card** → sweeps Fable 5 (rare ; on n'a que Willison+CursorBench).
2. **Opus 4.7 card** (→ 3ᵉ source indépendante pour `opus-4.7@medium` = dernier jaune → vert),
   **Sonnet 4.6 card**, **Haiku 4.5 card**.
Pour chacun : mêmes groupes (un par benchmark), source `anthropic-<model>-syscard`, effort explicite,
coûts digitalisés `digitized-logx`, jamais de valeur brute inter-benchmark (ratios only).

## Rappels état projet (voir aussi HANDOFF.md)
- 2 grilles data-driven via `gen/build.py::ratio_grid(field)` : `cost_grid()`=ratios de `cost_usd`,
  `quality_grid()`=ratios de `score`. Injectées `__COSTGRID__`/`__QUALGRID__` dans app.js.
- §1 landscape : X=coût relatif, Y=qualité relative, **ellipse ±1σ** par point. Haiku exclu du §1.
- §3 GROUPS généré depuis le CSV (`groups_data()`). §6 régime no-think. Pareto dédié.
- Corroboration (dernier état connu) : ~0 rouge ; `opus-4.7@medium` = orange (CursorBench seul).
- Branche `task/improve`. Build : `python3 gen/build.py` → `cost-matrix.html`.
