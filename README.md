# cc-formation-optimizer

Outil Python d'aide à l'organisation des sessions de formation des
coordonnateurs communaux (CC) pour les communes PC/TPC de l'EAR 2027.

Le projet contient deux parties distinctes :

1. un modèle d'optimisation sous contraintes, basé sur OR-Tools CP-SAT ;
2. une surcouche métier post-optimisation, optionnelle, qui relit une solution
   exportée et propose des ajustements possibles.

La surcouche métier ne remplace pas le modèle, ne relance pas le solveur et ne
modifie jamais les exports produits par l'optimisation. Elle produit uniquement
des fichiers de propositions à examiner.

## Présentation du projet

Le projet répartit des communes dans des sessions de formation en tenant compte
des catégories PC/TPC, des communes pivots, des temps de trajet, des capacités en
CC et des budgets de formations. L'objectif est de produire une solution
contrôlée, lisible et exploitable par les équipes métier.

Le modèle courant utilise notamment :

- un seuil maximal de trajet `T` ;
- une capacité maximale de session `Q` et un remplissage minimal `L` ;
- des budgets `B`, `f`, `k` avec `B = f + k` ;
- des slots pivots `M_PC = 3` et `M_TPC = 1` ;
- une interdiction stricte d'affecter une commune PC à une session TPC.

## Problème traité

Le problème consiste à affecter chaque commune à une session de formation
ouverte, avec une commune pivot pour chaque session. La solution doit respecter
les contraintes du modèle tout en restant compréhensible :

- toutes les communes doivent être affectées une seule fois ;
- les sessions doivent respecter les capacités en nombre de CC ;
- les temps de trajet absents ou supérieurs au seuil configuré ne sont pas
  admissibles ;
- les budgets de sessions PC/TPC doivent être respectés ;
- les résultats doivent être validables, exportables et interprétables ;
- les alertes territoriales, les mélanges PC/TPC autorisés et les trajets longs
  doivent rester visibles pour l'arbitrage métier.

## Fonctionnement général

Le pipeline principal suit ces étapes :

1. préparation des données brutes ou chargement de CSV propres ;
2. diagnostic pré-résolution ;
3. construction des paramètres dérivés ;
4. construction du modèle CP-SAT ;
5. résolution stricte ou avec assouplissements hiérarchiques ;
6. extraction de la solution métier ;
7. validation indépendante ;
8. exports CSV, Markdown, JSON, YAML, XLSX optionnel et carte HTML optionnelle ;
9. surcouche métier post-optimisation, si elle est demandée.

## Installation

Le projet principal et `travel_time_core` demandent tous les deux Python 3.12
minimum. Il n'est pas necessaire de creer une venv dans le depot pour installer
les dependances.

Depuis la racine du dépôt :

```powershell
python -m pip install -r requirements.txt
```

Si l'installation doit se faire sans droits administrateur :

```powershell
python -m pip install --user -r requirements.txt
```

Pour exposer aussi la commande console du projet principal :

```powershell
python -m pip install -e .
```

La commande devient alors disponible :

```powershell
cc-formation-optimizer --help
```

## Configuration

La configuration principale est :

```text
config/config_ear2027.yaml
```

Elle déclare les chemins d'entrée, les noms de colonnes, les paramètres du
modèle, les paramètres solveur, les assouplissements et les options d'exports.
Elle pilote notamment `T`, `Q`, `L`, les budgets `B`, `f`, `k`, les pondérations
d'objectif et les niveaux d'assouplissement.

État actuel de `config/config_ear2027.yaml` :

```text
T=60, Q=14, L=6
B=55, f=50, k=5
M_PC=3, M_TPC=1
w_t=100, w_e=1000, w_m=20
time_limit_seconds=1200, num_workers=8, random_seed=1
```

Le fichier suivant documente le schéma attendu :

```text
config/schema.yaml
```

Pour le détail des champs et des invariants, voir
[`docs/03_configuration_yaml.md`](docs/03_configuration_yaml.md).

## Données d'entrée recommandées

Le chemin recommandé est de préparer manuellement les CSV propres attendus par
l'optimiseur, plutôt que d'utiliser systématiquement la commande `prepare-data`.
Cette commande reste disponible pour convertir des fichiers bruts `.ods`, mais
elle est surtout utile comme outil ponctuel d'import. Pour un usage maîtrisé, il
vaut mieux placer directement les fichiers propres dans :

```text
data/processed/
```

### Communes

Nom attendu par la configuration courante :

```text
data/processed/communes_clean.csv
```

Colonnes obligatoires :

```text
code_commune,nom_commune,population,categorie
```

Colonnes optionnelles utiles :

```text
territoire_EAR,logements,latitude,longitude
```

Règles :

- `code_commune` : identifiant de commune, utilisé comme clé dans tous les
  autres fichiers ;
- `categorie` : uniquement `PC` ou `TPC` ;
- `population` : entier positif ou nul, utilisé pour calculer le nombre de CC ;
- `latitude` et `longitude` : optionnelles, mais nécessaires pour la carte HTML.

### Temps de trajet

Nom attendu par la configuration courante :

```text
data/processed/temps_trajet_clean.csv
```

Colonnes obligatoires :

```text
code_commune_origine,code_commune_pivot,temps_minutes
```

Règles :

- chaque ligne représente un trajet orienté `origine -> pivot` ;
- `temps_minutes` doit être un entier positif ou nul ;
- les trajets absents sont interdits par le modèle ;
- les trajets supérieurs au seuil `T` configuré ne sont pas admissibles ;
- il est recommandé d'inclure les diagonales `commune -> même commune` avec
  `temps_minutes = 0`.

### Liaisons bloquées optionnelles

Par défaut, toutes les liaisons disposant d'un temps de trajet admissible sont
compatibles métier (`b_ij = 1`). Pour bloquer explicitement certaines liaisons,
créer un fichier :

```text
data/processed/compatibilites_clean.csv
```

Colonnes obligatoires :

```text
code_commune_origine,code_commune_pivot,compatible
```

Règles :

- `compatible = 0` signifie que la liaison est interdite (`b_ij = 0`) ;
- `compatible = 1` signifie que la liaison est autorisée ;
- les lignes absentes restent autorisées par défaut ;
- tous les codes doivent exister dans `communes_clean.csv`.

Pour activer ce fichier, renseigner aussi dans `config/config_ear2027.yaml` :

```yaml
inputs:
  compatibility_path: data/processed/compatibilites_clean.csv
```

## Commandes principales

### Lancer l'exécution guidée

```powershell
cc-formation-optimizer guided-run --config config/config_ear2027.yaml
```

Guide un utilisateur non expert et enchaîne les contrôles utiles : fichiers
bruts, préparation, contrôle des diagonales de temps de trajet, diagnostic,
optimisation, exports, carte et surcouche métier. Les étapes longues comme le
calcul des temps de trajet et le solveur demandent toujours confirmation.

Options utiles :

- `--yes` : confirme automatiquement les étapes courtes ;
- `--skip-travel-times` : ne lance pas `travel_time_core` ;
- `--skip-solve` : ne lance pas le solveur ;
- `--skip-map` : ne régénère pas la carte seule ;
- `--skip-postprocess` : ne lance pas la surcouche métier ;
- `--input-dir`, `--processed-dir`, `--output-dir` : remplacent les dossiers par défaut.

Voir [`docs/12_execution_guidee.md`](docs/12_execution_guidee.md).

### Valider la configuration

```bash
cc-formation-optimizer validate-config --config config/config_ear2027.yaml
```

Vérifie que la configuration respecte les invariants attendus par le code.

### Afficher un résumé de configuration

```bash
cc-formation-optimizer show-config --config config/config_ear2027.yaml
```

Affiche les principaux paramètres métier : `T`, `Q`, `L`, `B`, `f`, `k`,
`M_PC` et `M_TPC`.

### Option secondaire : préparer les données depuis les fichiers bruts

```bash
cc-formation-optimizer prepare-data --config config/config_ear2027.yaml --input-dir donnee_brut_EAR27 --output-dir data/processed --report
```

Cette commande lit les fichiers bruts `.ods`, applique les mappings déclarés
dans le YAML et produit les CSV propres dans `data/processed/`. Elle est utile
si les fichiers bruts doivent être convertis, mais le flux recommandé reste de
fournir directement les CSV propres décrits plus haut. Avec `--report`, elle
écrit :

- `outputs/reports/rapport_preparation_donnees.md` ;
- `outputs/reports/statistiques_preparation_donnees.json`.

Options utiles :

- `--dry-run` : analyse sans écrire de fichiers ;
- `--strict` : échoue en présence d'anomalies bloquantes.

### Diagnostiquer avant résolution

```bash
cc-formation-optimizer diagnose --config config/config_ear2027.yaml
```

Charge les données propres, construit les paramètres dérivés et affiche les
volumes, la borne minimale de formations, les trajets admissibles et les alertes
pré-résolution.

### (ATTENTION cela ne renvoi aucun résultat) Résoudre strictement le modèle

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml
```

Construit le modèle CP-SAT, lance le solveur, extrait la solution et exécute la
validation. Sans option d'export, la commande affiche un résumé mais n'écrit pas
les fichiers de solution.

### Résoudre et exporter

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml --export --map --output-dir outputs
```

Produit les exports après validation. `--map` ajoute la carte HTML autonome.
Aucun export exploitable n'est produit si la validation échoue.

### Résoudre avec assouplissements hiérarchiques

```bash
cc-formation-optimizer solve-relaxed --config config/config_ear2027.yaml --export --map --output-dir outputs
```

`solve-relaxed` teste d'abord la configuration initiale, puis applique les
niveaux d'assouplissement configurés jusqu'à trouver une solution validée ou
épuiser les niveaux. La contrainte PC vers session TPC n'est pas relâchée
automatiquement.

### Régénérer uniquement la carte

```bash
cc-formation-optimizer render-map --config config/config_ear2027.yaml --solution-dir outputs
```

Relit les exports existants et régénère `outputs/maps/solution_map.html` sans
relancer le solveur.

### Lancer la surcouche métier post-optimisation

```bash
cc-formation-optimizer postprocess-business-rules \
  --config config/config_ear2027.yaml \
  --input-dir outputs \
  --output-dir outputs/postprocess \
  --min-travel-time-gain-min 5
```

Cette commande relit les exports de l'optimisation, applique les règles métier
post-optimisation et écrit des fichiers de propositions dans le dossier passé à
`--output-dir`.

## Résultats produits

### Sorties de l'optimisation

Avec `--export`, les fichiers principaux sont :

- `outputs/solutions/sessions.csv` : une ligne par session ouverte, avec pivot,
  type, capacité, remplissage, temps de trajet, volumes PC/TPC et alertes ;
- `outputs/solutions/communes_affectees.csv` : une ligne par commune affectée,
  avec session, pivot, type, temps de trajet et alertes ;
- `outputs/reports/rapport_solution.md` : rapport lisible de la solution ;
- `outputs/reports/statistiques_solution.json` : indicateurs globaux,
  objectifs, warnings et violations éventuelles ;
- `outputs/reports/config_utilisee.yaml` : copie de la configuration utilisée ;
- `outputs/solutions/solution_formations.xlsx` : export optionnel si
  `openpyxl` est disponible ;
- `outputs/maps/solution_map.html` : carte HTML autonome si `--map` est utilisé.

Avec `solve-relaxed`, des fichiers de suivi peuvent aussi être produits :

- `outputs/reports/journal_assouplissements.json` ;
- `outputs/reports/rapport_assouplissements.md` ;
- `outputs/reports/config_finale.yaml` si une solution validée est retenue.

### Sorties de la surcouche métier

La surcouche écrit ses résultats dans le dossier passé via `--output-dir`. Pour
la commande standard :

```bash
--output-dir outputs/postprocess
```

les fichiers attendus sont :

```text
outputs/postprocess/business_reallocation_proposals.csv
outputs/postprocess/business_reallocation_summary.csv
```

`business_reallocation_proposals.csv` contient les propositions détaillées de
changement. `business_reallocation_summary.csv` contient une synthèse par règle.
Les fichiers produits par l'optimisation initiale ne sont pas modifiés.

## Surcouche métier post-optimisation

La surcouche métier analyse une solution déjà exportée et signale des situations
qui peuvent mériter un arbitrage. Elle ne modifie pas les sessions, ne déplace
pas automatiquement les communes et ne cherche pas à optimiser une nouvelle
fonction objectif.

Les règles actuellement implémentées sont :

- `R1` : pour les sessions TPC dont le pivot ne participe pas à la formation,
  proposer un pivot interne qui minimise les temps de trajet ;
- `R2` : pour une commune pivot absente de sa propre formation, proposer son
  rattachement à cette formation, même si certaines limites du modèle peuvent
  être dépassées ;
- `R3` : pour une commune plus proche d'un autre pivot de même type PC/TPC,
  proposer une réaffectation si le gain de trajet dépasse le seuil choisi.

Les propositions peuvent être contradictoires. Les colonnes
`model_constraints_respected`, `warning` et `conflict_hint` aident à identifier
les cas compatibles avec les contraintes détectables et ceux qui demandent un
arbitrage métier.

Voir [`docs/11_surcouche_metier_post_optimisation.md`](docs/11_surcouche_metier_post_optimisation.md).

## Organisation du dépôt

- `config/` : configuration YAML et schéma documentaire.
- `data/` : données brutes et données transformées ; les données réelles
  préparées sont ignorées par Git.
- `docs/` : documentation détaillée.
- `donnee_brut_EAR27/` : fichiers bruts locaux, ignorés par Git.
- `outputs/` : exports générés, ignorés par Git sauf fichiers `.gitkeep`.
- `src/cc_formation_optimizer/` : package Python principal.
- `src/cc_formation_optimizer/business_postprocess/` : surcouche métier
  post-optimisation.
- `travel_time_core/` : sous-projet indépendant de génération des matrices de
  temps ; il communique avec l'optimiseur uniquement par fichiers CSV/ODS.
- `tests/` : tests automatisés et fixtures.

## Génération des matrices de temps

Le dossier `travel_time_core/` contient un sous-projet indépendant permettant de
produire les matrices de temps de trajet. Il peut exporter un
`temps_trajet_clean.csv` compatible avec l'optimiseur, sans import Python direct
entre les deux projets. Voir [`travel_time_core/README.md`](travel_time_core/README.md).

## Documentation détaillée

- [`docs/00_vue_ensemble.md`](docs/00_vue_ensemble.md) : vue rapide du flux
  complet.
- [`docs/01_donnees_entree.md`](docs/01_donnees_entree.md) : données attendues.
- [`docs/02_modelisation_mathematique.md`](docs/02_modelisation_mathematique.md) :
  formulation mathématique synthétique.
- [`docs/03_configuration_yaml.md`](docs/03_configuration_yaml.md) :
  configuration YAML.
- [`docs/04_resolution_et_assouplissements.md`](docs/04_resolution_et_assouplissements.md) :
  solveur et protocole d'assouplissement.
- [`docs/05_validation_solution.md`](docs/05_validation_solution.md) :
  contrôles de validation.
- [`docs/06_format_exports.md`](docs/06_format_exports.md) : format des exports.
- [`docs/07_visualisation_cartographique.md`](docs/07_visualisation_cartographique.md) :
  carte HTML.
- [`docs/08_preparation_donnees.md`](docs/08_preparation_donnees.md) :
  préparation des données réelles.
- [`docs/09_modelisation_algorithmique_complete.md`](docs/09_modelisation_algorithmique_complete.md) :
  document principal pour comprendre l'algorithme complet.
- [`docs/09_modelisation_algorithmique_complete.tex`](docs/09_modelisation_algorithmique_complete.tex) :
  version LaTeX autonome de la modélisation algorithmique.
- [`docs/09_modelisation_algorithmique_complete.pdf`](docs/09_modelisation_algorithmique_complete.pdf) :
  version PDF compilée lorsque l'outillage LaTeX est disponible ; les sources
  `.md` et `.tex` font foi si le PDF n'a pas pu être régénéré localement.
- [`docs/10_contexte_llm.md`](docs/10_contexte_llm.md) :
  contexte technique structuré pour reprise par un LLM.
- [`docs/11_surcouche_metier_post_optimisation.md`](docs/11_surcouche_metier_post_optimisation.md) :
  documentation dédiée à la surcouche métier.
- [`docs/12_execution_guidee.md`](docs/12_execution_guidee.md) :
  guide utilisateur de la commande interactive `guided-run`.
- [`docs/rapport_technique_complet.tex`](docs/rapport_technique_complet.tex) :
  document LaTeX consolidé couvrant la modélisation, les exports, la surcouche
  métier et l'annexe de production des matrices de temps.

## Tests

```bash
pytest
```

## État actuel et limites

Un statut solveur `FEASIBLE` signifie qu'une solution valide a été trouvée, mais
que l'optimalité n'est pas prouvée. La validation indépendante reste donc
indispensable avant toute exploitation.

Plusieurs décisions restent métier :

- le pivot doit-il obligatoirement participer à sa propre session ?
- accepte-t-on des sessions multi-territoires ?
- accepte-t-on les TPC dans des sessions PC, comportement autorisé par le
  modèle actuel ?
- faut-il pénaliser plus fortement les trajets longs ?
- faut-il réduire le nombre de sessions ou seulement respecter le plafond ?

Le projet fournit une solution contrôlée, des exports traçables et des
propositions post-optimisation ; il ne remplace pas l'arbitrage métier final.
