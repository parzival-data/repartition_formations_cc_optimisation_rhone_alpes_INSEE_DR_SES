# Résumé de passation — Optimisation des formations CC EAR 2027

## 1. But du projet

Ce projet optimise la répartition des communes PC/TPC dans des sessions de
formation de coordonnateurs communaux (CC) pour l'EAR 2027. Il choisit des
communes pivots, ouvre des sessions, affecte chaque commune à une session, puis
vérifie les contraintes de capacité, de trajets, de budgets, de type PC/TPC et
de validation post-solution.

Le périmètre actuel couvre la préparation des données réelles, la construction
d'un modèle OR-Tools CP-SAT, la résolution stricte ou assouplie, l'extraction
d'une solution métier, la validation automatique, les exports CSV/JSON/Markdown
et la carte HTML de contrôle. La solution produite reste une aide à la décision :
une revue métier finale est nécessaire.

## 2. État actuel du dépôt

État Git avant rédaction de ce document :

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

Derniers commits importants observés avec `git log --oneline -15` :

```text
374b3a1 docs: fix latex rendering in algorithmic documentation
8f9beac docs: simplify algorithmic latex notation
8597376 docs: polish complete algorithmic documentation
9d33142 docs: align documentation with implemented pipeline
7329dfc chore: increase EAR 2027 solver time limit
d967df4 feat: improve map legend and layout
6eb1180 docs: add complete algorithmic formulation
8134abe chore: update EAR 2027 solver parameters
5350751 fix: repair pivots-only map filter
57e27cd fix: correct map projection and tile rendering
91b2505 feat: integrate commune coordinates
5371384 feat: add real data preparation workflow
7eb4bda feat: add hierarchical relaxation workflow
b6fabcd feat: add interactive map export
e5db649 feat: add final solution exports
```

Résultat des tests avant rédaction :

```text
72 passed
```

Commandes CLI disponibles dans `src/cc_formation_optimizer/cli.py` :

- `validate-config`
- `show-config`
- `prepare-data`
- `diagnose`
- `solve`
- `solve-relaxed`
- `render-map`

Modules principaux présents :

- `config.py` : chargement et validation YAML.
- `data_preparation.py` : transformation des fichiers bruts ODS/CSV en CSV propres.
- `data_loading.py` : chargement des CSV propres.
- `parameters.py` : ensembles et paramètres dérivés.
- `diagnostics.py` : diagnostic pré-résolution.
- `model_builder.py` : modèle CP-SAT.
- `solver.py` : appel OR-Tools CP-SAT.
- `solution_extractor.py` : extraction métier depuis les variables solveur.
- `validation.py` : validation post-solution.
- `export.py` : exports CSV, JSON, Markdown, YAML et XLSX optionnel.
- `map_export.py` : carte HTML autonome.
- `relaxation.py` : workflow `solve-relaxed`.

La commande installée `cc-formation-optimizer` n'était pas disponible dans
l'environnement courant pendant cette passation. Le projet reste configuré pour
l'exposer via `pyproject.toml` après installation en mode développement.

## 3. Architecture du dépôt

`config/` contient la configuration principale `config_ear2027.yaml` et un
`schema.yaml` documentaire. Les paramètres métier actuels sont notamment
`T=75`, `Q=14`, `L=6`, `B=55`, `f=45`, `k=10`, `w_t=1`, `w_e=1000`, `w_m=500`.
Le solveur courant est configuré à `time_limit_seconds=2400`, `num_workers=8`,
`random_seed=1` et `log_search_progress=true`.

`data/` contient les sous-dossiers `raw/`, `processed/` et `samples/`. Les
fichiers réels préparés dans `data/processed/` sont ignorés par Git, sauf les
`.gitkeep`.

`docs/` contient la documentation de projet. `docs/09_modelisation_algorithmique_complete.md`
est le document principal pour comprendre le pipeline et le modèle actuel.

`src/cc_formation_optimizer/` contient le package Python et toute la logique de
préparation, optimisation, validation, export et carte.

`tests/` contient 72 tests automatisés, des fixtures minimales CSV/YAML et des
tests couvrant configuration, chargement, paramètres, modèle, solveur,
extraction, validation, exports, carte, préparation de données, relaxation et
CLI.

`outputs/` contient des sorties générées : rapports, solutions CSV et carte.
Ces fichiers sont ignorés par Git, sauf les `.gitkeep`.

`donnee_brut_EAR27/` contient les fichiers ODS réels. Ce dossier est ignoré par
Git.

Le `.gitignore` ignore notamment `donnee_brut_EAR27/`, `donnee_brut_EAR2027/`,
`data/processed/*`, `outputs/**/*.csv`, `outputs/**/*.xlsx`,
`outputs/**/*.md`, `outputs/**/*.html`, `outputs/**/*.json` et
`outputs/**/*.yaml`.

## 4. Données réelles

Le dossier brut réel est `donnee_brut_EAR27/`. Les fichiers ODS détectés sont :

- `cities_geocoded.ods`
- `info_minimum.ods`
- `matrice_temps_trajets_complete.ods`
- `matrice_temps_trajets_max_120min.ods`
- `matrice_temps_trajets_max_60min.ods`
- `matrice_temps_trajets_max_90min.ods`
- `villes_rhone_alpes.ods`

Le fichier de coordonnées est `cities_geocoded.ods`, feuille `cities`, avec les
colonnes `insee_code`, `name`, `lat`, `lon` et des colonnes de contrôle
ignorées par le solveur.

Les fichiers préparés actuels sont :

- `data/processed/communes_clean.csv`
- `data/processed/temps_trajet_clean.csv`

Aucun fichier de compatibilités n'est actuellement chargé. Le modèle pose donc
`b_ij = 1` par défaut pour les compatibilités absentes.

Chiffres importants issus des statistiques de préparation et des exports :

- 543 communes.
- 342 PC.
- 201 TPC.
- 573 CC.
- 47 698 trajets dans le fichier préparé et admissibles avec `T=75`.
- 543/543 coordonnées jointes.
- 0 coordonnée invalide.
- 0 commune sans coordonnées.
- Borne minimale mentionnée dans l'historique utilisateur : 53 formations.
- Point à noter : avec la configuration courante `Q=14`, la borne mécanique
  `ceil(573 / 14)` vaut 41. La valeur 53 semble donc correspondre à un
  scénario ou une contrainte antérieure, ou à une borne métier plus forte que la
  seule capacité.

Les données brutes, les CSV préparés et les outputs sont ignorés par Git. Ne pas
les ajouter à un commit sauf demande explicite.

## 5. Pipeline complet

Le flux complet est :

```text
configuration YAML
-> prepare-data
-> chargement CSV propres
-> construction des paramètres
-> diagnostic
-> modèle CP-SAT
-> solve / solve-relaxed
-> extraction
-> validation
-> exports
-> carte HTML
-> analyse métier
```

Responsabilités par étape :

- Configuration YAML : `config.py` charge `config/config_ear2027.yaml` et vérifie les invariants.
- Préparation : `data_preparation.py` lit les ODS/CSV bruts, normalise les codes, catégories, coordonnées et temps.
- Chargement : `data_loading.py` lit les CSV propres configurés.
- Paramètres : `parameters.py` construit `C`, `P`, `T`, `F`, `S`, `q_i`, `tau_ij`, `a_ij`, `b_ij`, `e_j_PC`, `e_j_TPC`.
- Diagnostic : `diagnostics.py` calcule les volumes, slots, trajets admissibles, orphelins et alertes budget.
- Modèle : `model_builder.py` crée les variables CP-SAT et les contraintes.
- Résolution stricte : `solver.py` lance OR-Tools CP-SAT avec les paramètres du YAML.
- Assouplissement : `relaxation.py` teste une hiérarchie de configurations dérivées.
- Extraction : `solution_extractor.py` transforme les valeurs solveur en sessions et affectations.
- Validation : `validation.py` recalcule contraintes et objectifs depuis la solution métier.
- Exports : `export.py` produit les fichiers de restitution après validation.
- Carte : `map_export.py` produit ou régénère `solution_map.html`.
- Analyse métier : lecture des exports, notamment `outputs/reports/analyse_solution_reelle.md` si disponible.

## 6. Modèle mathématique résumé

Ensembles :

- `C` : communes à affecter.
- `P` : communes PC.
- `T` : communes TPC. Ne pas confondre avec le seuil de trajet `T`.
- `F = C` : toute commune est candidate pivot.
- `S = {(j,m) : j in F, m in 1..M_j}` : sessions candidates.

Paramètres :

- `q_i` : nombre de CC de la commune `i`, égal à 1 si population <= 5000, sinon 2.
- `tau_ij` : temps de trajet orienté de `i` vers `j`.
- `a_ij` : admissibilité trajet, égale à 1 si le trajet existe et respecte le seuil `T`.
- `b_ij` : compatibilité métier, égale à 1 par défaut si aucun fichier de compatibilité n'est chargé.
- `T` : temps maximal de trajet.
- `Q` : capacité maximale d'une session en CC.
- `L` : remplissage minimal d'une session ouverte.
- `B`, `f`, `k` : budget total, budget PC et budget TPC, avec `B = f + k`.
- `e_j^PC`, `e_j^TPC` : coûts d'éligibilité d'un pivot.
- `w_t`, `w_e`, `w_m` : poids de trajet, éligibilité et mixité.

Variables :

- `x_ijm` : vaut 1 si la commune `i` est affectée à la session `(j,m)`.
- `y_jm` : vaut 1 si la session `(j,m)` est ouverte.
- `z_jm` : vaut 1 si la session `(j,m)` est de type TPC, 0 si elle est PC.
- `d_jm` : mixité résiduelle, nombre de CC TPC affectés à une session PC.

Objectif :

- composante trajet : somme des `q_i * tau_ij * x_ijm` ;
- composante éligibilité : coût du pivot selon le type de session ;
- composante mixité : somme des `d_jm` ;
- objectif total : `w_t * trajet + w_e * éligibilité + w_m * mixité`.

Contraintes principales :

- affectation unique de chaque commune ;
- aucune affectation vers une session fermée ;
- charge entre `L` et `Q` pour chaque session ouverte ;
- cohérence `z_jm <= y_jm` ;
- budgets PC et TPC ;
- ordre d'ouverture des slots pour les pivots PC ;
- interdiction d'affecter une commune PC à une session TPC ;
- définition de la mixité résiduelle.

Point de vigilance métier majeur : actuellement, le pivot n'est pas forcément
affecté à sa propre session. Donc une session TPC peut avoir une commune pivot
PC si cette commune PC n'est pas affectée à cette session. Ce comportement est
autorisé par le modèle actuel et constitue une question métier à trancher.

## 7. Commandes principales

Commandes PowerShell utiles, à écrire sur une seule ligne :

```powershell
pip install -e .
```

```powershell
pytest
```

```powershell
cc-formation-optimizer validate-config --config config/config_ear2027.yaml
```

```powershell
cc-formation-optimizer prepare-data --config config/config_ear2027.yaml --input-dir donnee_brut_EAR27 --output-dir data/processed --report
```

```powershell
cc-formation-optimizer diagnose --config config/config_ear2027.yaml
```

```powershell
cc-formation-optimizer solve --config config/config_ear2027.yaml
```

```powershell
cc-formation-optimizer solve --config config/config_ear2027.yaml --export --map --output-dir outputs/real_run_initial
```

```powershell
cc-formation-optimizer solve-relaxed --config config/config_ear2027.yaml --export --map --output-dir outputs/real_run_relaxed
```

```powershell
cc-formation-optimizer render-map --config config/config_ear2027.yaml --solution-dir outputs/real_run_initial
```

Ne pas utiliser `\` pour couper une commande PowerShell. Utiliser une seule
ligne, ou le backtick PowerShell si une coupure est vraiment nécessaire.

## 8. Résultats de résolution connus

Les exports présents dans `outputs/` décrivent une résolution réelle :

- statut solveur : `FEASIBLE` ;
- validation : `OK` ;
- objectif total : 148759 ;
- `Obj_trajet` : 18259 ;
- `Obj_eligibilite` : 100 ;
- `Obj_mixite` : 61 ;
- 55 sessions ouvertes ;
- 45 sessions PC ;
- 10 sessions TPC ;
- 543 communes affectées ;
- 573 CC ;
- temps moyen global : 32.54 min ;
- temps maximal global : 74 min ;
- 17 sessions saturées ;
- aucune violation exportée.

Le statut `FEASIBLE` signifie que la solution respecte les contraintes et a été
validée, mais que l'optimalité n'est pas prouvée. Elle est donc candidate, pas
nécessairement définitive.

La solution sature les budgets actuels : `B=55/55`, `f=45/45`, `k=10/10`.
La borne minimale mentionnée dans l'historique utilisateur est 53 formations,
ce qui place cette solution à +2 sessions. Avec `Q=14`, la borne mécanique par
capacité seule vaut 41.

Le temps solveur d'environ 1200 s vient de l'historique utilisateur et de la
configuration copiée dans `outputs/reports/config_utilisee.yaml`
(`time_limit_seconds: 1200`). La configuration courante du dépôt a depuis été
augmentée à 2400 s.

## 9. Exports produits

Les exports sont produits uniquement après extraction et validation.

Fichiers de solution :

- `outputs/solutions/sessions.csv` : une ligne par session ouverte avec pivot,
  type, charge, remplissage, temps, mixité, coûts et alertes.
- `outputs/solutions/communes_affectees.csv` : une ligne par commune avec
  session, pivot, trajet, catégorie, territoire, population et alertes.
- `outputs/solutions/solution_formations.xlsx` : export optionnel si
  `openpyxl` est disponible. Il n'est pas présent dans les outputs actuels.

Rapports :

- `outputs/reports/rapport_solution.md` : synthèse lisible de la solution.
- `outputs/reports/statistiques_solution.json` : statistiques structurées.
- `outputs/reports/config_utilisee.yaml` : copie de la configuration utilisée
  lors de la résolution.
- `outputs/reports/analyse_solution_reelle.md` : analyse métier existante des exports.
- `outputs/reports/rapport_preparation_donnees.md` et
  `outputs/reports/statistiques_preparation_donnees.json` : rapport et stats de préparation.

Carte :

- `outputs/maps/solution_map.html` : carte HTML autonome.

Assouplissement :

- `journal_assouplissements.json`
- `rapport_assouplissements.md`
- `config_finale.yaml`

Ces fichiers ne sont produits que par `solve-relaxed`. Ils ne sont pas présents
dans les outputs actuels à la racine `outputs/`.

## 10. Carte HTML

La carte est générée par `map_export.py`. Elle produit un HTML autonome avec du
JavaScript natif, un SVG pour les points et les liaisons, et un fond externe
IGN/Géoplateforme WMTS.

Données JavaScript embarquées :

- `globalStats`
- `validationChecks`
- `points`
- `summary`
- `missingCoordinates`

Caractéristiques :

- fond IGN/Géoplateforme via `https://data.geopf.fr/wmts` ;
- projection Web Mercator côté navigateur ;
- points PC/TPC avec forme différente ;
- pivots plus visibles ;
- alertes par contour ;
- filtres par territoire, type de session, catégorie, alerte, pivots seulement ;
- liaisons commune -> pivot optionnelles ;
- légende intégrée ;
- panneau debug carte ;
- fallback si le fond WMTS ne charge pas ;
- `render-map` régénère la carte depuis les exports sans relancer le solveur.

Bugs corrigés dans l'historique récent :

- projection Web Mercator et rendu des tuiles ;
- fond de carte WMTS ;
- filtre "pivots seulement" ;
- légende et mise en page ;
- rendu LaTeX de la documentation algorithmique.

## 11. Documentation

Documents importants :

- `docs/00_vue_ensemble.md` : synthèse du pipeline.
- `docs/01_donnees_entree.md` : données attendues et préparation.
- `docs/02_modelisation_mathematique.md` : formulation mathématique courte.
- `docs/03_configuration_yaml.md` : paramètres YAML.
- `docs/04_resolution_et_assouplissements.md` : solveur et relaxation.
- `docs/05_validation_solution.md` : validation post-solution.
- `docs/06_format_exports.md` : fichiers exportés.
- `docs/07_visualisation_cartographique.md` : carte HTML.
- `docs/08_preparation_donnees.md` : workflow données réelles.
- `docs/09_modelisation_algorithmique_complete.md` : document principal pour
  comprendre l'algorithme complet, de la donnée brute aux exports.
- `docs/10_resume_passation_ia.md` : ce résumé autonome de reprise.

## 12. Points de vigilance techniques

- Ne pas utiliser de backslash `\` pour couper les commandes PowerShell.
- Ne pas confondre `render-map` et `solve` : `render-map` ne relance pas le solveur.
- Modifier le YAML ne change pas les anciens exports.
- Relancer `solve` pour appliquer des paramètres d'optimisation modifiés.
- Relancer `prepare-data` pour appliquer des changements de fichiers bruts ou de matrice.
- Vérifier `config_utilisee.yaml` dans les outputs pour savoir avec quels paramètres une solution a été produite.
- Ne pas commit `data/processed`, `outputs` ou les données brutes.
- `validate-config` peut seulement afficher une ligne de succès si tout va bien.
- La commande console peut être indisponible tant que `pip install -e .` n'a pas été exécuté.
- La configuration courante et les exports existants peuvent différer : ici, solveur 2400 s dans le YAML courant, 1200 s dans `config_utilisee.yaml`.
- Les noms accentués de certains exports existants apparaissent mal encodés dans certains affichages PowerShell, mais les fichiers sont écrits en UTF-8.

## 13. Points de vigilance métier / modèle

- Le pivot n'est pas forcément affecté à sa propre session.
- Une session TPC avec pivot PC est possible si le pivot PC n'est pas affecté à cette session.
- Les trajets absents sont interdits, car aucune variable `x_ijm` n'est créée.
- Les coûts très élevés sont des pénalités, pas des interdictions.
- Une solution `FEASIBLE` n'est pas forcément optimale.
- Les superviseurs, calendriers et disponibilités ne sont pas optimisés.
- Le territoire EAR n'est pas une contrainte dure dans le modèle actuel.
- La validation métier finale reste nécessaire après validation algorithmique.
- Le nombre de formations est souvent saturé à 55 avec les paramètres actuels.
- Il faut analyser les sessions peu remplies, les pivots multiples, les trajets
  longs, la mixité TPC dans sessions PC et les sessions multi-territoires.

Signaux observés dans l'analyse existante :

- 18 sessions dont le pivot n'est pas affecté à cette session.
- 7 pivots accueillent au moins une formation sans participer à une session qu'ils portent.
- 25 sessions PC contiennent au moins une TPC.
- 61/201 communes TPC sont affectées à des formations PC.
- 45 sessions sont multi-territoires.
- 16 communes ont un trajet proche du seuil `T` (>= 68 min).

Ces signaux ne sont pas des violations du modèle actuel.

## 14. Prochaines tâches possibles

Priorité proposée :

1. Analyser les exports réels et produire un rapport métier final.
2. Décider si le pivot doit obligatoirement appartenir à sa propre session.
3. Si oui, ajouter les trajets diagonaux `j -> j = 0` nécessaires et une contrainte du type `x_jjm = y_jm`, en documentant précisément le choix.
4. Benchmarker `workers` et `time_limit_seconds`.
5. Ajouter des options CLI `--time-limit` et `--workers` si le besoin de scénarios rapides se confirme.
6. Calibrer les coûts et poids `w_t`, `w_e`, `w_m`.
7. Ajouter une pénalité d'ouverture si l'objectif métier est d'éviter les 55 sessions ouvertes quand une solution plus compacte est acceptable.
8. Ajouter une pénalité territoriale si les sessions multi-territoires doivent être réduites.
9. Améliorer les analyses automatiques d'anomalies apparentes.
10. Finaliser la documentation pour le rapport de stage.

## 15. Règles pour la future IA

Quand une nouvelle IA reprend :

- commencer par `git status`, `git log --oneline -15` et `pytest` ;
- relire `README.md` et `docs/10_resume_passation_ia.md` ;
- relire `docs/09_modelisation_algorithmique_complete.md` avant toute modification de modèle ;
- ne pas modifier le modèle sans demande explicite ;
- ne pas modifier les paramètres métier sans demande explicite ;
- ne pas commit si les tests échouent ;
- ne pas relancer `solve` ou `solve-relaxed` sur les données réelles sans accord, car la résolution peut être longue ;
- ne pas toucher aux données ignorées sauf demande ;
- ne pas commit `donnee_brut_EAR27/`, `data/processed/` ou `outputs/` ;
- faire des commits courts et ciblés ;
- documenter toute modification de modèle dans `docs/02_modelisation_mathematique.md` et `docs/09_modelisation_algorithmique_complete.md` ;
- toujours distinguer une correction de rendu/documentation d'un changement mathématique réel.
