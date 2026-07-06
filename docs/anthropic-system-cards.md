# Anthropic System Cards — registre & état d'intégration

But : incorporer les données **coût + qualité par effort** des System Cards Anthropic dans `raw-data.csv`,
puis `python3 gen/build.py`. Les grilles coût et qualité sont **couple-atomiques ROBUSTES** : ratios à tâche
identique intra-benchmark → normalisation de chaque benchmark à l'ancre `opus-4.8@medium = 1.0` (÷ ancre, ou
pont ×0,5 si absente) → **médiane pondérée** (poids = nb de sources) pour le centre, **MAD** pour la bande
(±1σ robuste). On ne compare **jamais** des valeurs brutes entre benchmarks — uniquement des **ratios au sein
d'un même benchmark**. Benchmarks à couple unique exclus. Haiku 4.5 = nœud `solo` (pas de molette d'effort).

## Liste EXHAUSTIVE des System Cards (source : anthropic.com/system-cards, juillet 2026)

| Modèle | Date | Pages | PDF direct | Priorité | État |
|---|---|---|---|---|---|
| **Sonnet 5** | 2026-06-30 | 145 | https://www-cdn.anthropic.com/9e6a1044980d8c4ed85669faf9c2a8342e2e9f1e/Claude%20Sonnet%205%20System%20Card.pdf | — | ✅ **INTÉGRÉ** |
| **Fable 5 & Mythos 5** | 2026-06-30 | 319 | https://www-cdn.anthropic.com/d00db56fa754a1b115b6dd7cb2e3c342ee809620.pdf | ★★★ (sweeps Fable) | ✅ **INTÉGRÉ** |
| **Opus 4.8** | 2026-05-28 | 246 | https://www-cdn.anthropic.com/0f0c97ad20d8005706296bd92aa1c27c6b2f4f61/Claude%20Opus%204.8%20System%20Card.pdf (alt hash: 0b4915911bb0d19eca5b5ee635c80fef830a37ea.pdf) | ★★★ (sweeps Opus 4.8/4.7 → comble opus-4.7@medium) | ✅ **INTÉGRÉ** |
| **Opus 4.7** | 2026-04-16 | 232 | https://www-cdn.anthropic.com/037f06850df7fbe871e206dad004c3db5fd50340/Claude%20Opus%204.7%20System%20Card.pdf | ★★ | ✅ **INTÉGRÉ** |
| **Sonnet 4.6** | 2026-02-17 | 134 | https://www-cdn.anthropic.com/78073f739564e986ff3e28522761a7a0b4484f84.pdf | ★★ | ✅ **TRAITÉ** (rien à intégrer) |
| **Opus 4.6** | 2026-02 | ? | https://www-cdn.anthropic.com/14e4fb01875d2a69f646fa5e574dea2b1c0ff7b5.pdf (alt: 0dd865075ad3132672ee0ab40b05a53f14cf5288.pdf, 6a5fa276ac68b9aeb0c8b6af5fa36326e0e166dd.pdf) | ★ (legacy) | ⏳ |
| **Mythos Preview** | 2026-04 | ? | page: anthropic.com/claude-mythos-preview-system-card | ☆ (config recherche) | ⏳ |
| Opus 4.5 | 2025-11 | ? | https://www-cdn.anthropic.com/bf10f64990cfda0ba858290be7b8cc6317685f47.pdf | ☆ legacy | — |
| Haiku 4.5 | 2025-10 | 39 | https://www-cdn.anthropic.com/7aad69bf12627d42234e01ee7c36305dc2f6a970.pdf | ★ (Haiku, pas d'effort discret) | ✅ **TRAITÉ** (rien à intégrer) |
| Sonnet 4.5 | 2025-09 | ? | https://www-cdn.anthropic.com/963373e433e489a87a10c823c52a0a013e9172dd.pdf | ☆ legacy | — |
| Opus 4.1 | 2025-08 | ? | https://www-cdn.anthropic.com/9fa30625273bafdf5af82c93719d7ca606485a16.pdf | ☆ legacy | — |
| Sonnet 4 & Opus 4 | 2025-05 | ? | https://www-cdn.anthropic.com/07b2a3f9902ee19fe39a36ca638e5ae987bc64dd.pdf (alt 6be99a52..., 4263b940...) | ☆ legacy | — |
| Sonnet 3.7 | 2025-02 | ? | https://www-cdn.anthropic.com/9ff93dfa8f445c932415d335c88852ef47f1201e.pdf | ☆ legacy | — |
| Haiku 3.5 & Sonnet 3.5 | 2024-10 | ? | https://www-cdn.anthropic.com/c7822cdc35ad788ec87e14b3a9d45010f1f86c38.pdf | ☆ trop vieux | — |
| Claude 3 | 2024-03 | ? | https://www-cdn.anthropic.com/c6a80a657af445f40e31afac050f3bf76d3b1404.pdf | ☆ | — |
| Claude 2 | 2023-07 | ? | https://www-cdn.anthropic.com/bd2a28d2535bfb0494cc8e2a3bf135d2e7523226/Model-Card-Claude-2.pdf | ☆ | — |

Modèles courants de la grille : Fable 5, Opus 4.8, Opus 4.7, Sonnet 5, Sonnet 4.6, Haiku 4.5.
→ **TOUTES traitées** (voir sections détaillées + synthèse en bas). Rien de prioritaire ne reste.

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
  cost-pts 119→142. (MàJ : la card Opus 4.7 étant aussi `anthropic-syscard`, elle NE rend PAS medium vert —
  il faudrait une source NON-Anthropic ; medium reste l'unique jaune.)

## ✅ Fable 5 & Mythos 5 System Card — INTÉGRÉ (2026-07-06, source=`anthropic-syscard`, ref `anthropic-fable5-syscard-pNNN`)

319 pages. **DÉCISION CLÉ (confirmée par l'utilisateur) : « Fable 5 = Mythos 5 avec plus de sécurités » →
on considère les deux ÉGAUX.** Les figures effort×coût du card tracent la ligne « Claude Mythos 5 » (= Fable 5
déployé, à ~0.3 pt près dû au fallback sécurité vers Opus 4.8 sur ~21 % des essais Terminal-Bench). Preuves
d'équivalence : la ligne Mythos 5 de **FrontierCode Main** (37.3/41.1/42.9/46.3/44.7) et de **CursorBench**
(max 72.9 %) coïncide EXACTEMENT avec nos données `scfrontiercode`/`cursorbench` déjà étiquetées « Fable 5 ».
« Claude Mythos Preview » (config recherche antérieure) reste HORS grille → ignoré.

**Avantage : coûts lus DIRECTEMENT en $/tâche sur l'axe x** (pas de conversion tokens→prix). Opus 4.8 co-tracé
sur chaque figure = ancre → Fable 5 placé directement. 5 groupes dédiés (couple-atomique intra-figure) ajoutés
comme `fable-5` + `opus-4.8`, confound `digitized-logx-mythos` :
- **`scfsweppro`** (fig 8.2.A p255, SWE-bench Pro) — Fable low→xhigh 75.0/78.2/79.6/80.4 ; Opus4.8 60.3/65.2/67.5/68.6.
- **`scfcdiamond`** (fig 8.4.A p257, FrontierCode Diamond) — Fable 11.5/17.8/24.0/29.3/30.9 ; Opus4.8 8.2/**5.9**/8.7/13.4/11.4 (inversion med<low RÉELLE, digitalisée fidèlement).
- **`scfdeepqa`** (fig 8.14.3.B p270, DeepSearchQA F1) — Fable 92.0/94.1/93.6/94.5/94.2 ; Opus4.8 88.6/90.1/91.0/92.1/93.1.
- **`scfhletools`** (fig 8.14.1.B p267, HLE avec outils) — Fable 59.8/62.6/63.4/64.2/64.5 ; Opus4.8 50.2/55.2/55.7/57.6/57.9 (coûts $ = `schletools` ✓ confirme la digitalisation).
- **`scfdraco`** (fig 8.14.4.A p271, DRACO) — Fable 76.7/80.6/82.8/84.9/86.4 ; Opus4.8 70.2/73.3/75.1/79.0/80.6.
- **SAUTÉ** (doublons) : FrontierCode Main (= `scfrontiercode`), CursorBench (= `cursorbench`).
- **Résultat** : tous les nœuds Fable 5 à 3–5 sources indépendantes (verts), σ resserré ; ladders coût
  (1.56→5.94) et qualité (1.18→1.33) monotones. Corroboration inchangée **vert 24 · jaune 1** ; cost-pts 142→166.
- Table 8.1 p252 (scores @xhigh/max) et autres barres lues mais non ajoutées (score-only, gain marginal).

## ✅ Opus 4.7 System Card — INTÉGRÉ (2026-07-06, source=`anthropic-syscard`, ref `anthropic-opus47-syscard-pNNN`)

232 pages. Compare Opus 4.7 vs Opus 4.6 (legacy) + GPT/Gemini — **Sonnet 4.6 absent** des figures (sauf
DeepSearchQA). Seul Opus 4.7 (+ Sonnet 4.6 sur une figure) est in-grid. **N.B. ce card est aussi `anthropic-syscard`
→ ne peut PAS rendre `opus-4.7@medium` vert** (même source) ; il resserre σ. 2 groupes ajoutés :
- **`scoarc`** (fig 8.11.A p213, ARC-AGI-2, coût $ direct) — Opus 4.7 low→max 61.9/66.0/68.0/75.8 (pas de xhigh).
- **`scodeepqa`** (fig 8.8.3.B p200, DeepSearchQA TTC, tokens totaux→$ 5:1) — Opus 4.7 80.6/86.0/88.6/88.1/89.9 +
  **Sonnet 4.6** 82.9/87.6/89.7/90.7 (seul vrai couple in-grid du card).
- **SAUTÉ** : HLE p197 (fig 8.8.1.B) = Opus 4.7 SEUL, valeurs 43.0/48.4/53.2/55.4/54.7 = doublon EXACT de `schleeff`.
- **Résultat** : ladders Opus 4.7 monotones, σ resserré ; corroboration inchangée **vert 24 · jaune 1** ; cost-pts 166→170.

## ✅ Sonnet 4.6 & Haiku 4.5 System Cards — TRAITÉS, RIEN À INTÉGRER (2026-07-06)

Ces deux cards **précèdent** l'ère des figures test-time-compute (effort×coût) et ne comparent qu'à des
modèles **legacy** hors grille → aucune arête couple-atomique in-grid possible. Vérifié :
- **Sonnet 4.6** (2026-02, 134 p) : Table 2.1.A compare Sonnet 4.6 vs Opus 4.6/4.5, Sonnet 4.5, Gemini 3 Pro,
  GPT-5.2 — **aucun partenaire in-grid**, pas de colonne coût, aucune figure de scaling par effort. `sonnet-4.6`
  déjà vert sur tous ses efforts via osworld/schletools/cursorbench/scosweff/scodeepqa/futuresearch.
- **Haiku 4.5** (2025-10, 39 p) : card sécurité ; compare vs Haiku 3.5, Sonnet 4.5, Opus 4.1 (legacy) ; Haiku n'a
  pas de molette d'effort (nœud `solo`) ; pas de coût. `haiku-4.5@solo` déjà vert.

## ✅ TOUTES les System Cards des modèles courants sont traitées
Sonnet 5 · Opus 4.8 · Fable 5/Mythos 5 · Opus 4.7 (intégrées) + Sonnet 4.6 · Haiku 4.5 (rien à intégrer).
État final : corroboration **vert 24 · jaune 1 · orange 0 · rouge 0** ; cost-pts 170. L'unique jaune
(`opus-4.7@medium`) ne passera vert que via une source **NON-Anthropic** mesurant opus-4.7@medium avec coût
(inexistante à ce jour — cf. HANDOFF). Cards legacy (Opus 4.6/4.5/4.1, Sonnet 4.5/4/3.7, Claude 3/2) = hors sujet.
Pour chacun : mêmes groupes (un par benchmark), source `anthropic-<model>-syscard`, effort explicite,
coûts digitalisés `digitized-logx`, jamais de valeur brute inter-benchmark (ratios only).

## Rappels état projet (voir aussi HANDOFF.md)
- 2 grilles data-driven via `gen/build.py::ratio_grid(field)` : `cost_grid()`=ratios de `cost_usd`,
  `quality_grid()`=ratios de `score`. Injectées `__COSTGRID__`/`__QUALGRID__` dans app.js.
- §1 landscape : X=coût relatif, Y=qualité relative, **ellipse = bande robuste MAD** par point. Haiku exclu du §1.
- §3 GROUPS généré depuis le CSV (`groups_data()`). §6 régime no-think. Pareto dédié.
- Corroboration (dernier état connu) : ~0 rouge ; `opus-4.7@medium` = orange (CursorBench seul).
- Branche `task/improve`. Build : `python3 gen/build.py` → `cost-matrix.html`.
