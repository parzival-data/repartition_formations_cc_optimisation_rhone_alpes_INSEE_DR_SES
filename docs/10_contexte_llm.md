# CONTEXTE LLM - cc-formation-optimizer

Version du contexte : 2026-07-01
Public cible : modèle LLM / agent de code autonome
Objectif : fournir une fenêtre de contexte suffisamment complété pour reprendre
le projet sans historique de conversation et sans lecture obligatoire du reste
du dépôt.

## 0. Règles d'utilisation pour un LLM

Ce fichier doit être traité comme une spécification de contexte, pas comme une
documentation utilisateur. Les informations ci-dessous sont alignees avec le
dépôt au moment de la rédaction.

Priorites pour toute IA qui reprend le projet :

1. Commencer par `git status --short`, `git log --oneline -15`, `pytest`, puis
   `pytest travel_time_core\tests` si le sous-projet de trajets est concerne.
2. Ne pas modifier le modèle mathématique sans demande explicite.
3. Ne pas modifier les paramètres métier YAML sans demande explicite.
4. Ne pas relancer `solve` ou `solve-relaxed` sur les données réelles sans accord
   explicite : la résolution peut être longue.
5. Ne pas commit `donnee_brut_EAR27/`, `data/processed/`, `outputs/` ni les
   fichiers ignorés.
6. Distinguer strictement :
   - optimisation principale ;
   - validation de solution ;
   - exports ;
   - carte ;
   - surcouche métier post-optimisation.
7. Une proposition post-optimisation n'est jamais une modification automatique
   de la solution optimisee.

## 1. Identite du projet

Nom Python : `cc-formation-optimizer`
Package : `src/cc_formation_optimizer/`
Commande console déclarée dans `pyproject.toml` :

```text
cc-formation-optimizer = cc_formation_optimizer.cli:main
```

But métier : organiser des sessions de formation de coordonnateurs communaux
(CC) pour les communes PC/TPC de l'EAR 2027.

Le projet a deux blocs fonctionnels :

1. Optimisation sous contraintes :
   - prépare ou chargé les données ;
   - construit un modèle OR-Tools CP-SAT ;
   - affecte les communes à des sessions ;
   - choisit les sessions ouvertes et leurs pivots ;
   - valide puis exporte une solution.
2. Surcouche métier post-optimisation :
   - relit les exports de la solution ;
   - détecte des situations étonnantes métier ;
   - produit des propositions argumentees ;
   - ne modifie jamais les exports d'optimisation.

## 2. État Git et tests connus

Derniers commits visibles :

```text
6faecba test: align config expectations
2160b27 docs: add numpy-style docstrings
6173c09 hjk
c5e165a gfds
197878f fds
f098244 feat: stabilize independent travel time core
4a4d2bc hjkl
07b9994 documentation
```

État fonctionnel vérifie recemment :

```text
pytest
81 passed

pytest travel_time_core\tests
31 passed
```

Attention : le nombre de tests peut changer. Toujours vérifier localement.

## 3. Architecture du dépôt

```text
config/
  config_ear2027.yaml
  schema.yaml

data/
  processed/
  raw/

docs/
  00_vue_ensemble.md
  01_donnees_entree.md
  02_modelisation_mathematique.md
  03_configuration_yaml.md
  04_resolution_et_assouplissements.md
  05_validation_solution.md
  06_format_exports.md
  07_visualisation_cartographique.md
  08_preparation_donnees.md
  09_modelisation_algorithmique_complete.md
  09_modelisation_algorithmique_complete.tex
  09_modelisation_algorithmique_complete.pdf
  10_contexte_llm.md
  11_surcouche_metier_post_optimisation.md

donnee_brut_EAR27/
outputs/
src/cc_formation_optimizer/
tests/
travel_time_core/
```

Sous-package principal :

```text
src/cc_formation_optimizer/
  cli.py
  config.py
  data_loading.py
  data_preparation.py
  diagnostics.py
  domain.py
  export.py
  logging_utils.py
  map_export.py
  model_builder.py
  parameters.py
  relaxation.py
  solution_extractor.py
  solver.py
  validation.py
  business_postprocess/
```

Surcouche métier :

```text
src/cc_formation_optimizer/business_postprocess/
  __init__.py
  io.py
  rules.py
  runner.py
  stats.py
  types.py
```

Tests :

```text
tests/
  test_cli.py
  test_cli_export.py
  test_cli_map.py
  test_cli_prepare_data.py
  test_cli_relaxation.py
  test_config.py
  test_data_loading.py
  test_data_preparation.py
  test_diagnostics.py
  test_end_to_end_small_instance.py
  test_export.py
  test_map_export.py
  test_model_builder_smoke.py
  test_parameters.py
  test_postprocess.py
  test_relaxation.py
  test_report_generation.py
  test_solution_extractor.py
  test_solver_small_instance.py
  test_validation.py
  fixtures/
```

Sous-projet de calcul des temps de trajet :

```text
travel_time_core/
  src/travel_times/
  tests/
  pyproject.toml
```

Il reste indépendant de l'optimiseur et communique avec lui par fichiers CSV/ODS.

## 4. Fichiers ignorés et règles de commit

Le `.gitignore` ignore notamment :

```text
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
*.egg-info/
donnee_brut_EAR2027/
donnee_brut_EAR27/
data/raw/*
data/processed/*
outputs/**/*.csv
outputs/**/*.xlsx
outputs/**/*.md
outputs/**/*.log
outputs/**/*.html
outputs/**/*.json
outputs/**/*.yaml
```

Exceptions : `.gitkeep` dans certains dossiers.

Règle : ne pas ajouter les données brutes, les CSV préparés ni les exports à un
commit, sauf demande explicite.

## 5. Configuration courante

Fichier principal : `config/config_ear2027.yaml`
Schéma documentaire : `config/schema.yaml`

Inputs configurés :

```text
communes_path: data/processed/communes_clean.csv
travel_times_path: data/processed/temps_trajet_clean.csv
compatibility_path: null
missing_travel_time_policy: forbidden
```

Colonnes principales :

```text
commune_id: code_commune
commune_name: nom_commune
population: population
category: categorie
territory_ear: territoire_EAR
housing: logements
latitude: latitude
longitude: longitude
origin_id: code_commune_origine
destination_id: code_commune_pivot
travel_time_minutes: temps_minutes
compatibility_allowed: compatible
```

Paramètres métier courants :

```text
T = 60
Q = 14
L = 6
B = 55
f = 50
k = 5
B = f + k
M_PC = 3
M_TPC = 1
w_t = 100
w_e = 1000
w_m = 20
threshold_population = 5000
q_i = 1 si population <= 5000, sinon 2
```

Solveur courant :

```text
time_limit_seconds = 1200
num_workers = 8
random_seed = 1
log_search_progress = true
```

Assouplissements configurés dans `relaxation` :

```text
w_m_values: [250, 100, 50]
tpc_eligibility_cost_factors: [0.75, 0.5, 0.25]
T_increase_factors: [1.10, 1.20, 1.30]
L_decrease_steps: [1, 2, 3]
Q_increase_steps: [1, 2, 5]
budget_increase_steps:
  f: [1, 2]
  k: [1, 2]
  B: [2, 4]
allow_replace_large_costs: true
large_cost_threshold: 1000000000
large_cost_replacement: 100000
```

Contraintes de validation config :

- `T > 0`
- `Q > 0`
- `0 < L <= Q`
- `B = f + k`
- `M_PC = 3`
- `M_TPC = 1`
- seuil population pour 2 CC = 5000
- poids objectifs strictement positifs
- coût `infinity` strictement positif

## 6. Données réelles locales

Dossier brut : `donnee_brut_EAR27/`

Fichiers bruts détectes :

```text
cities_geocoded.ods
info_minimum.ods
matrice_temps_trajets_complete.ods
matrice_temps_trajets_max_120min.ods
matrice_temps_trajets_max_60min.ods
matrice_temps_trajets_max_90min.ods
villes_rhone_alpes.ods
```

Fichier de coordonnées :

```text
donnee_brut_EAR27/cities_geocoded.ods
```

Fichiers préparés présents localement :

```text
data/processed/communes_clean.csv
data/processed/temps_trajet_clean.csv
```

Chiffres connus depuis les outputs/préparation :

```text
communes = 543
PC = 342
TPC = 201
CC = 573
trajets prepares dans `data/processed/temps_trajet_clean.csv` = 47 698
seuil courant d'admissibilite du modele T = 60
coordonnees = 543/543
```

Aucun fichier de compatibilité n'est actuellement chargé. Le modèle interprété
les compatibilités absentes comme autorisées par défaut (`b_ij = 1`).

## 7. CLI disponible

Le parseur est dans `src/cc_formation_optimizer/cli.py`.

Commandes :

```text
validate-config
show-config
prepare-data
diagnose
solve
solve-relaxed
render-map
postprocess-business-rules
```

Exemples :

```powershell
cc-formation-optimizer validate-config --config config/config_ear2027.yaml
```

```powershell
cc-formation-optimizer show-config --config config/config_ear2027.yaml
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
cc-formation-optimizer solve --config config/config_ear2027.yaml --export --map --output-dir outputs
```

```powershell
cc-formation-optimizer solve-relaxed --config config/config_ear2027.yaml --export --map --output-dir outputs
```

```powershell
cc-formation-optimizer render-map --config config/config_ear2027.yaml --solution-dir outputs
```

```powershell
cc-formation-optimizer postprocess-business-rules --config config/config_ear2027.yaml --input-dir outputs --output-dir outputs/postprocess --min-travel-time-gain-min 5
```

PowerShell : ne pas utiliser le backslash `\` comme continuation de ligne.

## 8. Pipeline principal

Pipeline strict :

```text
YAML config
-> data_loading
-> parameters
-> diagnostics optional
-> model_builder
-> solver
-> solution_extractor
-> validation
-> export optional
-> map optional
```

Pipeline avec préparation :

```text
raw ODS files
-> prepare-data
-> data/processed/*.csv
-> pipeline strict
```

Pipeline avec assouplissement :

```text
YAML config
-> attempt initial
-> if no accepted solution, apply relaxation levels
-> rebuild derived parameters/model each attempt
-> solve/extract/validate each attempt
-> keep first validated accepted solution
-> write relaxation reports
```

Surcouche post-optimisation :

```text
outputs/solutions/sessions.csv
outputs/solutions/communes_affectees.csv
config travel_times_path
config compatibility_path optional
-> business_postprocess runner
-> proposals CSV
-> summary CSV
```

## 9. Modules et responsabilites

`config.py`

- chargé YAML ;
- construit les dataclasses `OptimizerConfig`, `ModelParameters`, etc. ;
- valide les invariants métier.

`domain.py`

- dataclasses `Commune`, `TravelTime`, `Compatibility`, `FormationSlot`.

`data_preparation.py`

- lit les fichiers bruts ;
- normalisé communes, catégories, populations, logements, coordonnées ;
- prépare les temps de trajet ;
- écrit `communes_clean.csv`, `temps_trajet_clean.csv` et rapports.

`data_loading.py`

- lit les CSV propres selon `config.columns` ;
- leve `DataLoadingError` en cas de fichier/colonne invalide.

`parameters.py`

- construit les ensembles et paramètres dérivés ;
- calculé `q_i`, `M_j`, `S`, `tau_ij`, `a_ij`, `b_ij`, `e_j_PC`, `e_j_TPC`.

`diagnostics.py`

- calculé volumes, slots, trajets admissibles, orphelins et alertes budget.

`model_builder.py`

- construit le modèle CP-SAT ;
- cree les variables seulement pour les affectations admissibles et compatibles.

`solver.py`

- configuré OR-Tools CP-SAT depuis `config.solver` ;
- retourne statut, objectif, solveur et temps.

`solution_extractor.py`

- extrait `OpenSession`, `CommuneAssignment`, `ObjectiveBreakdown`,
  `ExtractedSolution`.

`validation.py`

- contrôle affectation unique, ouverture, capacité, budgets, PC/TPC, trajets,
  compatibilités, types de session, mixité et objectif recalculé.

`export.py`

- écrit les exports uniquement si validation OK ;
- produit CSV, JSON, Markdown, YAML et XLSX optionnel.

`map_export.py`

- produit ou régénère `solution_map.html`.

`relaxation.py`

- orchestre `solve-relaxed` ;
- écrit journal et rapport d'assouplissement.

`business_postprocess/`

- surcouche métier post-optimisation ;
- ne modifie pas les exports d'origine.

## 10. Modèle mathématique implémenté

Ensembles :

```text
C = communes
P = communes PC
T_set = communes TPC
F = C = pivots candidats
S = {(j,m) | j in F, m in 1..M_j}
```

Attention notation : `T` dans le YAML est le seuil de trajet. Dans le code,
`DerivedParameters.T` est l'ensemble des communes TPC.

Paramètres :

```text
q_i      nombre de CC de la commune i
tau_ij   temps de trajet oriente i -> j
a_ij     1 si trajet i -> j existe et tau_ij <= T
b_ij     compatibilite metier, 1 par défaut
T        seuil de trajet en minutes
Q        capacite maximale en CC
L        remplissage minimal
B,f,k    budgets total, PC, TPC
e_j_PC   cout eligibilite pivot j en session PC
e_j_TPC  cout eligibilite pivot j en session TPC
w_t,w_e,w_m poids objectif
```

Variables :

```text
x_ijm = 1 si commune i affectée a session (j,m)
y_jm  = 1 si session (j,m) ouverte
z_jm  = 1 si session (j,m) de type TPC, 0 si PC
d_jm  = mixite residuelle TPC dans session PC
```

Contraintes implémentées :

- chaque commune est affectée exactement une fois ;
- `x_ijm <= y_jm` ;
- chargé ouverte entre `L` et `Q` ;
- `z_jm <= y_jm` ;
- budgets PC/TPC ;
- ordre des slots PC ;
- interdiction PC dans session TPC ;
- définition de la mixité `d_jm`.

Important : le code ne force pas le pivot à être affecté à sa propre session.

Important : le territoire EAR n'est pas une contrainte dure. Il apparait dans
les exports et alertes.

Objectif :

```text
min w_t * O_trajet + w_e * O_eligibilite + w_m * O_mixite
```

Pas de coût fixe d'ouverture de session dans l'objectif actuel. Pas de pénalité
territoriale dans l'objectif actuel.

## 11. Résultats reels connus dans outputs/

Depuis `outputs/reports/statistiques_solution.json` :

```text
solver_status = FEASIBLE
validation_status = OK
objective_total = 2116880
obj_trajet = 12654
obj_eligibilite = 1100
obj_mixite = 152
nombre_communes = 543
nombre_communes_affectees = 543
nombre_CC = 573
sessions_ouvertes = 55
B = 55
sessions_PC = 50
f = 50
sessions_TPC = 5
k = 5
Q = 14
L = 6
T = 60
temps_moyen_global = 22.64
temps_max_global = 60
sessions_sous_remplies = 0
sessions_saturees = 14
violations = []
```

Attention : ces exports existants ont ete produits avec
`outputs/reports/config_utilisee.yaml`, qui indique `w_t = 80`, `w_e = 1000` et
`w_m = 30`. Le YAML courant `config/config_ear2027.yaml` indique maintenant
`w_t = 100`, `w_e = 1000` et `w_m = 20`. Ne pas presenter l'objectif total des
exports existants comme recalcule avec les poids courants sans relancer le
solveur ou recalculer explicitement la solution.

Warnings exportes :

```text
commune affectée a un pivot d'un territoire different
forte mixite TPC dans session PC
population tres dispersee
session multi-territoires
session proche de la capacite maximale
temps de trajet proche de T
temps_trajet_max proche de T
```

Interprétation :

- `FEASIBLE` = solution valide trouvée, optimalité non prouvée.
- La validation est OK.
- Les budgets sont satures : 55/55, 50/50, 5/5.
- La solution est exploitable comme candidate, pas comme preuve d'optimum.

## 12. Exports d'optimisation

Produits par `export.py` après validation OK.

Solutions :

```text
outputs/solutions/sessions.csv
outputs/solutions/communes_affectees.csv
outputs/solutions/solution_formations.xlsx  # optionnel, si openpyxl disponible
```

Rapports :

```text
outputs/reports/rapport_solution.md
outputs/reports/statistiques_solution.json
outputs/reports/config_utilisee.yaml
outputs/reports/rapport_preparation_donnees.md
outputs/reports/statistiques_preparation_donnees.json
```

Carte :

```text
outputs/maps/solution_map.html
```

Assouplissements possibles :

```text
outputs/reports/journal_assouplissements.json
outputs/reports/rapport_assouplissements.md
outputs/reports/config_finale.yaml
```

Ces fichiers peuvent ne pas exister si `solve-relaxed` n'a pas été exécuté.

## 13. Carte HTML

Module : `map_export.py`

Entrees :

```text
solution extraite + validation + communes
ou exports existants via render-map
```

Sortie :

```text
outputs/maps/solution_map.html
```

Caracteristiques :

- HTML autonome ;
- JS natif ;
- SVG pour points et liens ;
- fond WMTS `https://data.geopf.fr/wmts` ;
- projection Web Mercator cote navigateur ;
- données embarquées : `globalStats`, `validationChecks`, `points`, `summary`,
  `missingCoordinates` ;
- filtrès territoire/type/catégorie/alerte ;
- filtre pivots seulement ;
- liens commune -> pivot optionnels ;
- panneau debug carte ;
- fallback sans fond de carte.

## 14. Surcouche métier post-optimisation

Sous-package :

```text
src/cc_formation_optimizer/business_postprocess/
```

Point d'entrée Python :

```text
cc_formation_optimizer.business_postprocess.postprocess_business_rules
```

Commande CLI :

```powershell
cc-formation-optimizer postprocess-business-rules --config config/config_ear2027.yaml --input-dir outputs --output-dir outputs/postprocess --min-travel-time-gain-min 5
```

Sortie terminale attendue :

```text
Business post-processing completed.
Proposals written to: outputs/postprocess/business_reallocation_proposals.csv
Summary written to: outputs/postprocess/business_reallocation_summary.csv
Original optimization exports were not modified.
Number of proposals: <n>
Solveur: non relance
```

Fichiers produits :

```text
outputs/postprocess/business_reallocation_proposals.csv
outputs/postprocess/business_reallocation_summary.csv
```

Ces fichiers sont ignorés par Git.

Modules internes :

```text
types.py   dataclasses, constantes colonnes, noms de regles
io.py      lecture exports + temps + compatibilites, ecriture CSV
stats.py   statistiques avant/après, contraintes detectables
rules.py   R1, R2, R3
runner.py  orchestration, conflits, synthese
```

Règles :

R1 `Pivot interne pour formation TPC`

- cible les sessions TPC dont le pivot actuel n'est pas affecté à la session ;
- teste les communes affectées comme pivots internes candidats ;
- minimise le temps total, puis le temps max, puis population descendante, puis
  code commune ;
- ne change aucune affectation ;
- produit une proposition `proposal_scope = pivot_change_only`.

R2 `Rattacher une commune pivot a sa propre formation`

- pour chaque session, vérifie si la commune pivot est affectée à cette session ;
- sinon vérifie si elle est affectée à une autre session ou elle est aussi pivot ;
- si aucune condition n'est vraie, propose de retirer la commune de sa session
  actuelle et de l'ajouter à sa propre session ;
- peut violer capacité, L, type PC/TPC ou trajet ;
- la proposition est conservée avec `model_constraints_respected=false` si
  nécessaire.

R3 `Commune plus proche d'un autre pivot de meme type`

- pour chaque commune affectée, compare les autres sessions du même type PC/TPC ;
- si un pivot de même type est strictement plus proche et si le gain est au
  moins `min_travel_time_gain_min`, produit une proposition de reassignment ;
- ne compare pas les types différents ;
- contrôle capacité, L, trajet, compatibilité et PC dans TPC.

Conflits :

- `conflict_hint` signale si une commune ou une session apparait dans plusieurs
  propositions ;
- aucune résolution automatique des conflits ;
- les propositions sont indépendantes.

Résultat actuel de la surcouche sur `outputs/` :

```text
R1: 4 propositions, 3 compatibles, 1 non compatible, gain total 138
R2: 3 propositions, 0 compatibles, 3 non compatibles, gain total 86
R3: 6 propositions, 0 compatibles, 6 non compatibles, gain total 53
```

## 15. Tests

Commande :

```powershell
pytest
pytest travel_time_core\tests
```

État vérifie recemment :

```text
81 passed
31 passed dans travel_time_core
```

Tests de surcouche :

```text
tests/test_postprocess.py
```

Cas couverts :

- session TPC avec pivot externe -> proposition R1 ;
- session TPC avec pivot interne -> pas de proposition R1 ;
- pivot absent de sa propre session -> proposition R2 ;
- commune plus proche d'un pivot de même type -> proposition R3 ;
- pivot plus proche de type différent -> pas de R3 ;
- dépassement capacité conservé mais marque non compatible ;
- exports d'origine non modifiés ;
- CLI écrit les deux fichiers dans `--output-dir` ;
- import public via `business_postprocess`.

## 16. Documentation existante

Documents à connaître :

```text
README.md
docs/00_vue_ensemble.md
docs/01_donnees_entree.md
docs/02_modelisation_mathematique.md
docs/03_configuration_yaml.md
docs/04_resolution_et_assouplissements.md
docs/05_validation_solution.md
docs/06_format_exports.md
docs/07_visualisation_cartographique.md
docs/08_preparation_donnees.md
docs/09_modelisation_algorithmique_complete.md
docs/09_modelisation_algorithmique_complete.tex
docs/09_modelisation_algorithmique_complete.pdf
docs/10_contexte_llm.md
docs/11_surcouche_metier_post_optimisation.md
```

Rôle :

- `README.md` : document d'entrée humain.
- `docs/09_modelisation_algorithmique_complete.*` : explication complété du
  modèle et de l'algorithme. Si le PDF n'a pas été régénéré, les sources `.md`
  et `.tex` font foi.
- `docs/11_surcouche_metier_post_optimisation.md` : doc humaine de la surcouche.
- `docs/10_contexte_llm.md` : contexte technique pour IA.

## 17. Points de vigilance métier

Le modèle actuel autorisé explicitement ou implicitement :

- un pivot qui ne participe pas à sa propre session ;
- une session TPC portée par un pivot PC si ce pivot PC n'est pas affecté à la
  session ;
- des TPC dans des sessions PC ;
- des sessions multi-territoires ;
- des coûts très élevés comme pénalités, pas comme interdictions ;
- un statut `FEASIBLE` sans preuve d'optimalité.

Le modèle interdit :

- commune PC affectée à session TPC ;
- trajet absent ;
- trajet superieur au seuil `T` ;
- dépassement des budgets ;
- dépassement de capacité dans la solution optimisee validée.

Questions métier ouvertes :

- faut-il imposer que le pivot soit affecté à sa propre session ?
- faut-il interdire ou pénaliser les sessions multi-territoires ?
- faut-il réduire la présence TPC dans sessions PC ?
- faut-il pénaliser plus fortement les longs trajets ?
- faut-il réduire le nombre de sessions ouvertes ou seulement respecter `B` ?
- faut-il integrer superviseurs, calendriers, disponibilités ?

## 18. Points de vigilance techniques

- `render-map` ne relance jamais le solveur.
- `postprocess-business-rules` ne relance jamais le solveur.
- Modifier `config/config_ear2027.yaml` ne modifie pas les exports existants.
- Pour appliquer un YAML modifie, relancer `solve` ou `solve-relaxed`.
- Pour appliquer de nouvelles données brutes, relancer `prepare-data`.
- Vérifier `outputs/reports/config_utilisee.yaml` pour connaître la config qui a
  produit des exports existants.
- Le script console `cc-formation-optimizer` n'existe qu'après installation du
  package (`python -m pip install -e ".[dev]"` ou equivalent).
- En PowerShell, ne pas couper les commandes avec `\`.
- Les outputs locaux peuvent être présents mais ignorés par Git.

## 19. Procedures standard pour une IA

Audit initial :

```powershell
git status --short
git log --oneline -15
pytest
```

Vérifier configuration :

```powershell
cc-formation-optimizer validate-config --config config/config_ear2027.yaml
cc-formation-optimizer show-config --config config/config_ear2027.yaml
```

Vérifier données sans solve long :

```powershell
cc-formation-optimizer diagnose --config config/config_ear2027.yaml
```

Generer propositions post-optimisation :

```powershell
cc-formation-optimizer postprocess-business-rules --config config/config_ear2027.yaml --input-dir outputs --output-dir outputs/postprocess --min-travel-time-gain-min 5
```

Ne pas lancer sans accord :

```powershell
cc-formation-optimizer solve --config config/config_ear2027.yaml --export --map --output-dir outputs
cc-formation-optimizer solve-relaxed --config config/config_ear2027.yaml --export --map --output-dir outputs
```

## 20. Definition de "done" pour modifications futures

Pour une modification de code :

1. changements limites au perimêtre ;
2. tests existants et nouveaux tests pertinents ;
3. `pytest` OK ;
4. documentation mise à jour si comportement visible ;
5. `git status --short` inspecte ;
6. commit cible si demandé.

Pour une modification de modèle :

1. lire `model_builder.py`, `validation.py`, `parameters.py` ;
2. modifier la formulation ;
3. modifier la validation indépendante ;
4. modifier les docs mathématiques ;
5. ajouter tests unitaires et petit end-to-end ;
6. expliciter l'impact métier.

Pour une modification de surcouche métier :

1. ne pas toucher au solveur ;
2. ne pas modifier les exports d'origine ;
3. ajouter/adapter tests dans `tests/test_postprocess.py` ;
4. mettre à jour `docs/11_surcouche_metier_post_optimisation.md` si visible ;
5. mettre à jour ce fichier si la logique change.
