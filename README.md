# cc-formation-optimizer

Outil Python d'aide a l'organisation des sessions de formation des
coordonnateurs communaux (CC) pour les communes PC/TPC de l'EAR 2027.

Le projet contient deux parties distinctes :

1. un modele d'optimisation sous contraintes, base sur OR-Tools CP-SAT ;
2. une surcouche metier post-optimisation, optionnelle, qui relit une solution
   exportee et propose des ajustements possibles.

La surcouche metier ne remplace pas le modele, ne relance pas le solveur et ne
modifie jamais les exports produits par l'optimisation. Elle produit uniquement
des fichiers de propositions a examiner.

## Presentation du projet

Le projet repartit des communes dans des sessions de formation en tenant compte
des categories PC/TPC, des communes pivots, des temps de trajet, des capacites en
CC et des budgets de formations. L'objectif est de produire une solution
controlee, lisible et exploitable par les equipes metier.

Le modele courant utilise notamment :

- un seuil maximal de trajet `T` ;
- une capacite maximale de session `Q` et un remplissage minimal `L` ;
- des budgets `B`, `f`, `k` avec `B = f + k` ;
- des slots pivots `M_PC = 3` et `M_TPC = 1` ;
- une interdiction stricte d'affecter une commune PC a une session TPC.

## Probleme traite

Le probleme consiste a affecter chaque commune a une session de formation
ouverte, avec une commune pivot pour chaque session. La solution doit respecter
les contraintes du modele tout en restant comprehensible :

- toutes les communes doivent etre affectees une seule fois ;
- les sessions doivent respecter les capacites en nombre de CC ;
- les temps de trajet absents ou superieurs au seuil configure ne sont pas
  admissibles ;
- les budgets de sessions PC/TPC doivent etre respectes ;
- les resultats doivent etre validables, exportables et interpretables ;
- les alertes territoriales, les melanges PC/TPC autorises et les trajets longs
  doivent rester visibles pour l'arbitrage metier.

## Fonctionnement general

Le pipeline principal suit ces etapes :

1. preparation des donnees brutes ou chargement de CSV propres ;
2. diagnostic pre-resolution ;
3. construction des parametres derives ;
4. construction du modele CP-SAT ;
5. resolution stricte ou avec assouplissements hierarchiques ;
6. extraction de la solution metier ;
7. validation independante ;
8. exports CSV, Markdown, JSON, YAML, XLSX optionnel et carte HTML optionnelle ;
9. surcouche metier post-optimisation, si elle est demandee.

## Installation

Depuis la racine du depot :

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Sous PowerShell, l'activation de l'environnement virtuel s'ecrit plutot :

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

L'installation expose la commande :

```bash
cc-formation-optimizer --help
```

## Configuration

La configuration principale est :

```text
config/config_ear2027.yaml
```

Elle declare les chemins d'entree, les noms de colonnes, les parametres du
modele, les parametres solveur, les assouplissements et les options d'exports.
Elle pilote notamment `T`, `Q`, `L`, les budgets `B`, `f`, `k`, les ponderations
d'objectif et les niveaux d'assouplissement.

Le fichier suivant documente le schema attendu :

```text
config/schema.yaml
```

Pour le detail des champs et des invariants, voir
[`docs/03_configuration_yaml.md`](docs/03_configuration_yaml.md).

## Commandes principales

### Valider la configuration

```bash
cc-formation-optimizer validate-config --config config/config_ear2027.yaml
```

Verifie que la configuration respecte les invariants attendus par le code.

### Afficher un resume de configuration

```bash
cc-formation-optimizer show-config --config config/config_ear2027.yaml
```

Affiche les principaux parametres metier : `T`, `Q`, `L`, `B`, `f`, `k`,
`M_PC` et `M_TPC`.

### Preparer les donnees reelles

```bash
cc-formation-optimizer prepare-data --config config/config_ear2027.yaml --input-dir donnee_brut_EAR27 --output-dir data/processed --report
```

Cette commande lit les fichiers bruts `.ods`, applique les mappings declares
dans le YAML, produit les CSV propres dans `data/processed/` et, avec
`--report`, ecrit :

- `outputs/reports/rapport_preparation_donnees.md` ;
- `outputs/reports/statistiques_preparation_donnees.json`.

Options utiles :

- `--dry-run` : analyse sans ecrire de fichiers ;
- `--strict` : echoue en presence d'anomalies bloquantes.

### Diagnostiquer avant resolution

```bash
cc-formation-optimizer diagnose --config config/config_ear2027.yaml
```

Charge les donnees propres, construit les parametres derives et affiche les
volumes, la borne minimale de formations, les trajets admissibles et les alertes
pre-resolution.

### Resoudre strictement le modele

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml
```

Construit le modele CP-SAT, lance le solveur, extrait la solution et execute la
validation. Sans option d'export, la commande affiche un resume mais n'ecrit pas
les fichiers de solution.

### Resoudre et exporter

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml --export --map --output-dir outputs
```

Produit les exports apres validation. `--map` ajoute la carte HTML autonome.
Aucun export exploitable n'est produit si la validation echoue.

### Resoudre avec assouplissements hierarchiques

```bash
cc-formation-optimizer solve-relaxed --config config/config_ear2027.yaml --export --map --output-dir outputs
```

`solve-relaxed` teste d'abord la configuration initiale, puis applique les
niveaux d'assouplissement configures jusqu'a trouver une solution validee ou
epuiser les niveaux. La contrainte PC vers session TPC n'est pas relachee
automatiquement.

### Regenerer uniquement la carte

```bash
cc-formation-optimizer render-map --config config/config_ear2027.yaml --solution-dir outputs
```

Relit les exports existants et regenere `outputs/maps/solution_map.html` sans
relancer le solveur.

### Lancer la surcouche metier post-optimisation

```bash
cc-formation-optimizer postprocess-business-rules \
  --config config/config_ear2027.yaml \
  --input-dir outputs \
  --output-dir outputs/postprocess \
  --min-travel-time-gain-min 5
```

Cette commande relit les exports de l'optimisation, applique les regles metier
post-optimisation et ecrit des fichiers de propositions dans le dossier passe a
`--output-dir`.

## Resultats produits

### Sorties de l'optimisation

Avec `--export`, les fichiers principaux sont :

- `outputs/solutions/sessions.csv` : une ligne par session ouverte, avec pivot,
  type, capacite, remplissage, temps de trajet, volumes PC/TPC et alertes ;
- `outputs/solutions/communes_affectees.csv` : une ligne par commune affectee,
  avec session, pivot, type, temps de trajet et alertes ;
- `outputs/reports/rapport_solution.md` : rapport lisible de la solution ;
- `outputs/reports/statistiques_solution.json` : indicateurs globaux,
  objectifs, warnings et violations eventuelles ;
- `outputs/reports/config_utilisee.yaml` : copie de la configuration utilisee ;
- `outputs/solutions/solution_formations.xlsx` : export optionnel si
  `openpyxl` est disponible ;
- `outputs/maps/solution_map.html` : carte HTML autonome si `--map` est utilise.

Avec `solve-relaxed`, des fichiers de suivi peuvent aussi etre produits :

- `outputs/reports/journal_assouplissements.json` ;
- `outputs/reports/rapport_assouplissements.md` ;
- `outputs/reports/config_finale.yaml` si une solution validee est retenue.

### Sorties de la surcouche metier

La surcouche ecrit ses resultats dans le dossier passe via `--output-dir`. Pour
la commande standard :

```bash
--output-dir outputs/postprocess
```

les fichiers attendus sont :

```text
outputs/postprocess/business_reallocation_proposals.csv
outputs/postprocess/business_reallocation_summary.csv
```

`business_reallocation_proposals.csv` contient les propositions detaillees de
changement. `business_reallocation_summary.csv` contient une synthese par regle.
Les fichiers produits par l'optimisation initiale ne sont pas modifies.

## Surcouche metier post-optimisation

La surcouche metier analyse une solution deja exportee et signale des situations
qui peuvent meriter un arbitrage. Elle ne modifie pas les sessions, ne deplace
pas automatiquement les communes et ne cherche pas a optimiser une nouvelle
fonction objectif.

Les regles actuellement implementees sont :

- `R1` : pour les sessions TPC dont le pivot ne participe pas a la formation,
  proposer un pivot interne qui minimise les temps de trajet ;
- `R2` : pour une commune pivot absente de sa propre formation, proposer son
  rattachement a cette formation, meme si certaines limites du modele peuvent
  etre depassees ;
- `R3` : pour une commune plus proche d'un autre pivot de meme type PC/TPC,
  proposer une reaffectation si le gain de trajet depasse le seuil choisi.

Les propositions peuvent etre contradictoires. Les colonnes
`model_constraints_respected`, `warning` et `conflict_hint` aident a identifier
les cas compatibles avec les contraintes detectables et ceux qui demandent un
arbitrage metier.

Voir [`docs/11_surcouche_metier_post_optimisation.md`](docs/11_surcouche_metier_post_optimisation.md).

## Organisation du depot

- `config/` : configuration YAML et schema documentaire.
- `data/` : donnees brutes et donnees transformees ; les donnees reelles
  preparees sont ignorees par Git.
- `docs/` : documentation detaillee.
- `donnee_brut_EAR27/` : fichiers bruts locaux, ignores par Git.
- `outputs/` : exports generes, ignores par Git sauf fichiers `.gitkeep`.
- `src/cc_formation_optimizer/` : package Python principal.
- `src/cc_formation_optimizer/business_postprocess/` : surcouche metier
  post-optimisation.
- `tests/` : tests automatises et fixtures.

## Documentation detaillee

- [`docs/00_vue_ensemble.md`](docs/00_vue_ensemble.md) : vue rapide du flux
  complet.
- [`docs/01_donnees_entree.md`](docs/01_donnees_entree.md) : donnees attendues.
- [`docs/02_modelisation_mathematique.md`](docs/02_modelisation_mathematique.md) :
  formulation mathematique synthetique.
- [`docs/03_configuration_yaml.md`](docs/03_configuration_yaml.md) :
  configuration YAML.
- [`docs/04_resolution_et_assouplissements.md`](docs/04_resolution_et_assouplissements.md) :
  solveur et protocole d'assouplissement.
- [`docs/05_validation_solution.md`](docs/05_validation_solution.md) :
  controles de validation.
- [`docs/06_format_exports.md`](docs/06_format_exports.md) : format des exports.
- [`docs/07_visualisation_cartographique.md`](docs/07_visualisation_cartographique.md) :
  carte HTML.
- [`docs/08_preparation_donnees.md`](docs/08_preparation_donnees.md) :
  preparation des donnees reelles.
- [`docs/09_modelisation_algorithmique_complete.md`](docs/09_modelisation_algorithmique_complete.md) :
  document principal pour comprendre l'algorithme complet.
- [`docs/09_modelisation_algorithmique_complete.tex`](docs/09_modelisation_algorithmique_complete.tex) :
  version LaTeX autonome de la modelisation algorithmique.
- [`docs/09_modelisation_algorithmique_complete.pdf`](docs/09_modelisation_algorithmique_complete.pdf) :
  version PDF compilee.
- [`docs/10_resume_passation_ia.md`](docs/10_resume_passation_ia.md) :
  synthese de passation pour reprendre le projet.
- [`docs/11_surcouche_metier_post_optimisation.md`](docs/11_surcouche_metier_post_optimisation.md) :
  documentation dediee a la surcouche metier.

## Tests

```bash
pytest
```

## Etat actuel et limites

Un statut solveur `FEASIBLE` signifie qu'une solution valide a ete trouvee, mais
que l'optimalite n'est pas prouvee. La validation independante reste donc
indispensable avant toute exploitation.

Plusieurs decisions restent metier :

- le pivot doit-il obligatoirement participer a sa propre session ?
- accepte-t-on des sessions multi-territoires ?
- accepte-t-on les TPC dans des sessions PC, comportement autorise par le
  modele actuel ?
- faut-il penaliser plus fortement les trajets longs ?
- faut-il reduire le nombre de sessions ou seulement respecter le plafond ?

Le projet fournit une solution controlee, des exports tracables et des
propositions post-optimisation ; il ne remplace pas l'arbitrage metier final.
