# Format des exports

Les exports finaux sont produits uniquement apres extraction et validation de la solution par `validate_solution()`. Une solution invalide ne doit jamais etre exportee comme solution exploitable.

## Commande

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml --export
```

Par defaut, les fichiers sont produits sous `outputs/`. Un repertoire different peut etre indique avec `--output-dir`.

## Fichiers produits

### `outputs/solutions/sessions.csv`

Une ligne par session ouverte. Le fichier contient notamment :

- pivot, type de session et rang ;
- territoire majoritaire ;
- nombre de communes et nombre de CC ;
- capacite, taux de remplissage et places restantes ;
- statistiques de population et de temps de trajet ;
- volumes PC/TPC ;
- cout d'eligibilite et contributions d'objectif ;
- alertes metier non bloquantes.

### `outputs/solutions/communes_affectees.csv`

Une ligne par commune affectee. Le fichier contient notamment :

- commune, categorie, territoire, population et logements ;
- session et pivot retenus ;
- type de session ;
- temps de trajet utilise ;
- indicateurs `is_pivot` et `is_same_territory_as_pivot`;
- alertes metier non bloquantes.

### `outputs/reports/rapport_solution.md`

Rapport lisible par un utilisateur metier. Il reprend :

- date de generation ;
- configuration utilisee ;
- statut solveur et validation ;
- volumes de communes, CC et sessions ;
- rappel de `T`, `Q`, `L`, `B`, `f`, `k` ;
- objectif total et ses composantes ;
- contraintes validees ;
- alertes metier ;
- top 10 des sessions les plus longues, les moins remplies et les plus mixtes ;
- limites connues.

### `outputs/reports/statistiques_solution.json`

Synthese machine-readable pour archivage ou controle automatique :

- statuts solveur et validation ;
- objectifs ;
- volumes globaux ;
- budgets et parametres principaux ;
- temps moyen et maximal ;
- compteurs de sessions sous-remplies ou saturees ;
- violations et warnings.

### `outputs/reports/config_utilisee.yaml`

Copie exacte du fichier de configuration utilise pour la resolution. Elle garantit la reproductibilite de l'execution.

### `outputs/solutions/solution_formations.xlsx`

Export optionnel si `openpyxl` est disponible dans l'environnement. Il contient les onglets :

- `sessions` ;
- `communes_affectees` ;
- `statistiques` ;
- `validation` ;
- `configuration`.

Si la dependance n'est pas disponible, les exports CSV, Markdown, JSON et YAML restent produits.

### `outputs/maps/solution_map.html`

Export HTML autonome de controle visuel et metier. Il est produit avec :

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml --export --map
```

Les donnees sont embarquees directement dans le fichier HTML sous forme de constantes JavaScript :

- `globalStats` ;
- `validationChecks` ;
- `points` ;
- `summary`.

La carte utilise du JavaScript natif et un SVG pour dessiner les communes, les pivots et les liaisons optionnelles commune -> pivot. Les points restent visibles meme sans fond de carte externe. Les coordonnees latitude/longitude sont optionnelles : les communes sans coordonnees sont listees dans le panneau de controle et ne bloquent pas les autres exports.

## Alertes metier

Les alertes ne sont pas des violations de contraintes. Elles signalent des points a controler :

- session proche de la capacite maximale ;
- session faiblement remplie ;
- temps de trajet maximal proche de `T` ;
- session multi-territoires ;
- forte mixite TPC dans une session PC ;
- pivot avec cout d'eligibilite eleve ;
- population tres dispersee ;
- commune affectee a un pivot d'un territoire different.
