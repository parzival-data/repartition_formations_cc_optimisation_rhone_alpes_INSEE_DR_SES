# CONTEXTE LLM - cc-formation-optimizer

Version du contexte : 2026-06-25  
Public cible : modele LLM / agent de code autonome  
Objectif : fournir une fenetre de contexte suffisamment complete pour reprendre
le projet sans historique de conversation et sans lecture obligatoire du reste
du depot.

## 0. Regles d'utilisation pour un LLM

Ce fichier doit etre traite comme une specification de contexte, pas comme une
documentation utilisateur. Les informations ci-dessous sont alignees avec le
depot au moment de la redaction.

Priorites pour toute IA qui reprend le projet :

1. Commencer par `git status --short`, `git log --oneline -15`, puis `pytest`.
2. Ne pas modifier le modele mathematique sans demande explicite.
3. Ne pas modifier les parametres metier YAML sans demande explicite.
4. Ne pas relancer `solve` ou `solve-relaxed` sur les donnees reelles sans accord
   explicite : la resolution peut etre longue.
5. Ne pas commit `donnee_brut_EAR27/`, `data/processed/`, `outputs/` ni les
   fichiers ignores.
6. Distinguer strictement :
   - optimisation principale ;
   - validation de solution ;
   - exports ;
   - carte ;
   - surcouche metier post-optimisation.
7. Une proposition post-optimisation n'est jamais une modification automatique
   de la solution optimisee.

## 1. Identite du projet

Nom Python : `cc-formation-optimizer`  
Package : `src/cc_formation_optimizer/`  
Commande console declaree dans `pyproject.toml` :

```text
cc-formation-optimizer = cc_formation_optimizer.cli:main
```

But metier : organiser des sessions de formation de coordonnateurs communaux
(CC) pour les communes PC/TPC de l'EAR 2027.

Le projet a deux blocs fonctionnels :

1. Optimisation sous contraintes :
   - prepare ou charge les donnees ;
   - construit un modele OR-Tools CP-SAT ;
   - affecte les communes a des sessions ;
   - choisit les sessions ouvertes et leurs pivots ;
   - valide puis exporte une solution.
2. Surcouche metier post-optimisation :
   - relit les exports de la solution ;
   - detecte des situations etonnantes metier ;
   - produit des propositions argumentees ;
   - ne modifie jamais les exports d'optimisation.

## 2. Etat Git et tests connus

Derniers commits visibles :

```text
e6129fb readme
d314042 feat: add business postprocessing proposals
ddc34a6 docs: add algorithmic model latex document
2f31afd docs: add AI handoff summary
374b3a1 docs: fix latex rendering in algorithmic documentation
8f9beac docs: simplify algorithmic latex notation
8597376 docs: polish complete algorithmic documentation
9d33142 docs: align documentation with implemented pipeline
```

Etat fonctionnel verifie recemment :

```text
pytest
81 passed
```

Attention : le nombre de tests peut changer. Toujours verifier localement.

## 3. Architecture du depot

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

Surcouche metier :

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

## 4. Fichiers ignores et regles de commit

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

Regle : ne pas ajouter les donnees brutes, les CSV prepares ni les exports a un
commit, sauf demande explicite.

## 5. Configuration courante

Fichier principal : `config/config_ear2027.yaml`  
Schema documentaire : `config/schema.yaml`

Inputs configures :

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

Parametres metier courants :

```text
T = 75
Q = 14
L = 6
B = 55
f = 45
k = 10
B = f + k
M_PC = 3
M_TPC = 1
w_t = 1
w_e = 1000
w_m = 500
threshold_population = 5000
q_i = 1 si population <= 5000, sinon 2
```

Solveur courant :

```text
time_limit_seconds = 2400
num_workers = 8
random_seed = 1
log_search_progress = true
```

Assouplissements configures dans `relaxation` :

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
- cout `infinity` strictement positif

## 6. Donnees reelles locales

Dossier brut : `donnee_brut_EAR27/`

Fichiers bruts detectes :

```text
cities_geocoded.ods
info_minimum.ods
matrice_temps_trajets_complete.ods
matrice_temps_trajets_max_120min.ods
matrice_temps_trajets_max_60min.ods
matrice_temps_trajets_max_90min.ods
villes_rhone_alpes.ods
```

Fichier de coordonnees :

```text
donnee_brut_EAR27/cities_geocoded.ods
```

Fichiers prepares presents localement :

```text
data/processed/communes_clean.csv
data/processed/temps_trajet_clean.csv
```

Chiffres connus depuis les outputs/preparation :

```text
communes = 543
PC = 342
TPC = 201
CC = 573
trajets prepares/admissibles avec T=75 = 47 698
coordonnees = 543/543
```

Aucun fichier de compatibilite n'est actuellement charge. Le modele interprete
les compatibilites absentes comme autorisees par defaut (`b_ij = 1`).

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

Pipeline avec preparation :

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

- charge YAML ;
- construit les dataclasses `OptimizerConfig`, `ModelParameters`, etc. ;
- valide les invariants metier.

`domain.py`

- dataclasses `Commune`, `TravelTime`, `Compatibility`, `FormationSlot`.

`data_preparation.py`

- lit les fichiers bruts ;
- normalise communes, categories, populations, logements, coordonnees ;
- prepare les temps de trajet ;
- ecrit `communes_clean.csv`, `temps_trajet_clean.csv` et rapports.

`data_loading.py`

- lit les CSV propres selon `config.columns` ;
- leve `DataLoadingError` en cas de fichier/colonne invalide.

`parameters.py`

- construit les ensembles et parametres derives ;
- calcule `q_i`, `M_j`, `S`, `tau_ij`, `a_ij`, `b_ij`, `e_j_PC`, `e_j_TPC`.

`diagnostics.py`

- calcule volumes, slots, trajets admissibles, orphelins et alertes budget.

`model_builder.py`

- construit le modele CP-SAT ;
- cree les variables seulement pour les affectations admissibles et compatibles.

`solver.py`

- configure OR-Tools CP-SAT depuis `config.solver` ;
- retourne statut, objectif, solveur et temps.

`solution_extractor.py`

- extrait `OpenSession`, `CommuneAssignment`, `ObjectiveBreakdown`,
  `ExtractedSolution`.

`validation.py`

- controle affectation unique, ouverture, capacite, budgets, PC/TPC, trajets,
  compatibilites, types de session, mixite et objectif recalcule.

`export.py`

- ecrit les exports uniquement si validation OK ;
- produit CSV, JSON, Markdown, YAML et XLSX optionnel.

`map_export.py`

- produit ou regenere `solution_map.html`.

`relaxation.py`

- orchestre `solve-relaxed` ;
- ecrit journal et rapport d'assouplissement.

`business_postprocess/`

- surcouche metier post-optimisation ;
- ne modifie pas les exports d'origine.

## 10. Modele mathematique implemente

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

Parametres :

```text
q_i      nombre de CC de la commune i
tau_ij   temps de trajet oriente i -> j
a_ij     1 si trajet i -> j existe et tau_ij <= T
b_ij     compatibilite metier, 1 par defaut
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
x_ijm = 1 si commune i affectee a session (j,m)
y_jm  = 1 si session (j,m) ouverte
z_jm  = 1 si session (j,m) de type TPC, 0 si PC
d_jm  = mixite residuelle TPC dans session PC
```

Contraintes implementees :

- chaque commune est affectee exactement une fois ;
- `x_ijm <= y_jm` ;
- charge ouverte entre `L` et `Q` ;
- `z_jm <= y_jm` ;
- budgets PC/TPC ;
- ordre des slots PC ;
- interdiction PC dans session TPC ;
- definition de la mixite `d_jm`.

Important : le code ne force pas le pivot a etre affecte a sa propre session.

Important : le territoire EAR n'est pas une contrainte dure. Il apparait dans
les exports et alertes.

Objectif :

```text
min w_t * O_trajet + w_e * O_eligibilite + w_m * O_mixite
```

Pas de cout fixe d'ouverture de session dans l'objectif actuel. Pas de penalite
territoriale dans l'objectif actuel.

## 11. Resultats reels connus dans outputs/

Depuis `outputs/reports/statistiques_solution.json` :

```text
solver_status = FEASIBLE
validation_status = OK
objective_total = 148759
obj_trajet = 18259
obj_eligibilite = 100
obj_mixite = 61
nombre_communes = 543
nombre_communes_affectees = 543
nombre_CC = 573
sessions_ouvertes = 55
B = 55
sessions_PC = 45
f = 45
sessions_TPC = 10
k = 10
Q = 14
L = 6
T = 75
temps_moyen_global = 32.54
temps_max_global = 74
sessions_sous_remplies = 0
sessions_saturees = 17
violations = []
```

Warnings exportes :

```text
commune affectee a un pivot d'un territoire different
forte mixite TPC dans session PC
population tres dispersee
session multi-territoires
session proche de la capacite maximale
temps de trajet proche de T
temps_trajet_max proche de T
```

Interpretation :

- `FEASIBLE` = solution valide trouvee, optimalite non prouvee.
- La validation est OK.
- Les budgets sont satures : 55/55, 45/45, 10/10.
- La solution est exploitable comme candidate, pas comme preuve d'optimum.

## 12. Exports d'optimisation

Produits par `export.py` apres validation OK.

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

Ces fichiers peuvent ne pas exister si `solve-relaxed` n'a pas ete execute.

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
- donnees embarquees : `globalStats`, `validationChecks`, `points`, `summary`,
  `missingCoordinates` ;
- filtres territoire/type/categorie/alerte ;
- filtre pivots seulement ;
- liens commune -> pivot optionnels ;
- panneau debug carte ;
- fallback sans fond de carte.

## 14. Surcouche metier post-optimisation

Sous-package :

```text
src/cc_formation_optimizer/business_postprocess/
```

Point d'entree Python :

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

Ces fichiers sont ignores par Git.

Modules internes :

```text
types.py   dataclasses, constantes colonnes, noms de regles
io.py      lecture exports + temps + compatibilites, ecriture CSV
stats.py   statistiques avant/apres, contraintes detectables
rules.py   R1, R2, R3
runner.py  orchestration, conflits, synthese
```

Regles :

R1 `Pivot interne pour formation TPC`

- cible les sessions TPC dont le pivot actuel n'est pas affecte a la session ;
- teste les communes affectees comme pivots internes candidats ;
- minimise le temps total, puis le temps max, puis population descendante, puis
  code commune ;
- ne change aucune affectation ;
- produit une proposition `proposal_scope = pivot_change_only`.

R2 `Rattacher une commune pivot a sa propre formation`

- pour chaque session, verifie si la commune pivot est affectee a cette session ;
- sinon verifie si elle est affectee a une autre session ou elle est aussi pivot ;
- si aucune condition n'est vraie, propose de retirer la commune de sa session
  actuelle et de l'ajouter a sa propre session ;
- peut violer capacite, L, type PC/TPC ou trajet ;
- la proposition est conservee avec `model_constraints_respected=false` si
  necessaire.

R3 `Commune plus proche d'un autre pivot de meme type`

- pour chaque commune affectee, compare les autres sessions du meme type PC/TPC ;
- si un pivot de meme type est strictement plus proche et si le gain est au
  moins `min_travel_time_gain_min`, produit une proposition de reassignment ;
- ne compare pas les types differents ;
- controle capacite, L, trajet, compatibilite et PC dans TPC.

Conflits :

- `conflict_hint` signale si une commune ou une session apparait dans plusieurs
  propositions ;
- aucune resolution automatique des conflits ;
- les propositions sont independantes.

Resultat actuel de la surcouche sur `outputs/` :

```text
R1: 10 propositions, 10 compatibles, 0 non compatibles, gain total 751
R2: 7 propositions, 0 compatibles, 7 non compatibles, gain total 251
R3: 44 propositions, 5 compatibles, 39 non compatibles, gain total 611
```

## 15. Tests

Commande :

```powershell
pytest
```

Etat verifie recemment :

```text
81 passed
```

Tests de surcouche :

```text
tests/test_postprocess.py
```

Cas couverts :

- session TPC avec pivot externe -> proposition R1 ;
- session TPC avec pivot interne -> pas de proposition R1 ;
- pivot absent de sa propre session -> proposition R2 ;
- commune plus proche d'un pivot de meme type -> proposition R3 ;
- pivot plus proche de type different -> pas de R3 ;
- depassement capacite conserve mais marque non compatible ;
- exports d'origine non modifies ;
- CLI ecrit les deux fichiers dans `--output-dir` ;
- import public via `business_postprocess`.

## 16. Documentation existante

Documents a connaitre :

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

Role :

- `README.md` : document d'entree humain.
- `docs/09_modelisation_algorithmique_complete.*` : explication complete du
  modele et de l'algorithme.
- `docs/11_surcouche_metier_post_optimisation.md` : doc humaine de la surcouche.
- `docs/10_contexte_llm.md` : contexte technique pour IA.

## 17. Points de vigilance metier

Le modele actuel autorise explicitement ou implicitement :

- un pivot qui ne participe pas a sa propre session ;
- une session TPC portee par un pivot PC si ce pivot PC n'est pas affecte a la
  session ;
- des TPC dans des sessions PC ;
- des sessions multi-territoires ;
- des couts tres eleves comme penalites, pas comme interdictions ;
- un statut `FEASIBLE` sans preuve d'optimalite.

Le modele interdit :

- commune PC affectee a session TPC ;
- trajet absent ;
- trajet superieur au seuil `T` ;
- depassement des budgets ;
- depassement de capacite dans la solution optimisee validee.

Questions metier ouvertes :

- faut-il imposer que le pivot soit affecte a sa propre session ?
- faut-il interdire ou penaliser les sessions multi-territoires ?
- faut-il reduire la presence TPC dans sessions PC ?
- faut-il penaliser plus fortement les longs trajets ?
- faut-il reduire le nombre de sessions ouvertes ou seulement respecter `B` ?
- faut-il integrer superviseurs, calendriers, disponibilites ?

## 18. Points de vigilance techniques

- `render-map` ne relance jamais le solveur.
- `postprocess-business-rules` ne relance jamais le solveur.
- Modifier `config/config_ear2027.yaml` ne modifie pas les exports existants.
- Pour appliquer un YAML modifie, relancer `solve` ou `solve-relaxed`.
- Pour appliquer de nouvelles donnees brutes, relancer `prepare-data`.
- Verifier `outputs/reports/config_utilisee.yaml` pour connaitre la config qui a
  produit des exports existants.
- Le script console `cc-formation-optimizer` n'existe qu'apres installation du
  package (`python -m pip install -e ".[dev]"` ou equivalent).
- En PowerShell, ne pas couper les commandes avec `\`.
- Les outputs locaux peuvent etre presents mais ignores par Git.

## 19. Procedures standard pour une IA

Audit initial :

```powershell
git status --short
git log --oneline -15
pytest
```

Verifier configuration :

```powershell
cc-formation-optimizer validate-config --config config/config_ear2027.yaml
cc-formation-optimizer show-config --config config/config_ear2027.yaml
```

Verifier donnees sans solve long :

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

1. changements limites au perimetre ;
2. tests existants et nouveaux tests pertinents ;
3. `pytest` OK ;
4. documentation mise a jour si comportement visible ;
5. `git status --short` inspecte ;
6. commit cible si demande.

Pour une modification de modele :

1. lire `model_builder.py`, `validation.py`, `parameters.py` ;
2. modifier la formulation ;
3. modifier la validation independante ;
4. modifier les docs mathematiques ;
5. ajouter tests unitaires et petit end-to-end ;
6. expliciter l'impact metier.

Pour une modification de surcouche metier :

1. ne pas toucher au solveur ;
2. ne pas modifier les exports d'origine ;
3. ajouter/adapter tests dans `tests/test_postprocess.py` ;
4. mettre a jour `docs/11_surcouche_metier_post_optimisation.md` si visible ;
5. mettre a jour ce fichier si la logique change.
