# Format des exports

Les exports finaux sont produits uniquement après extraction et validation de la solution par `validate_solution()`. Une solution invalide ne doit jamais être exportée comme solution exploitable.

## Commande

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml --export
```

Par défaut, les fichiers sont produits sous `outputs/`. Un répertoire différent peut être indiqué avec `--output-dir`.

## Fichiers produits

### `outputs/solutions/sessions.csv`

Une ligne par session ouverte. Le fichier contient notamment :

- pivot, type de session et rang ;
- territoire majoritaire ;
- nombre de communes et nombre de CC ;
- capacité, taux de remplissage et places restantes ;
- statistiques de population et de temps de trajet ;
- volumes PC/TPC ;
- coût d'éligibilité et contributions d'objectif ;
- alertes métier non bloquantes.

### `outputs/solutions/communes_affectees.csv`

Une ligne par commune affectée. Le fichier contient notamment :

- commune, catégorie, territoire, population et logements ;
- session et pivot retenus ;
- type de session ;
- temps de trajet utilisé ;
- indicateurs `is_pivot` et `is_same_territory_as_pivot`;
- alertes métier non bloquantes.

### `outputs/reports/rapport_solution.md`

Rapport lisible par un utilisateur métier. Il reprend :

- date de génération ;
- configuration utilisée ;
- statut solveur et validation ;
- volumes de communes, CC et sessions ;
- rappel de `T`, `Q`, `L`, `B`, `f`, `k` ;
- objectif total et ses composantes ;
- contraintes validées ;
- alertes métier ;
- top 10 des sessions les plus longues, les moins remplies et les plus mixtes ;
- limites connues.

### `outputs/reports/statistiques_solution.json`

Synthèse machine-readable pour archivage ou contrôle automatique :

- statuts solveur et validation ;
- objectifs ;
- volumes globaux ;
- budgets et paramètres principaux ;
- temps moyen et maximal ;
- compteurs de sessions sous-remplies ou saturees ;
- violations et warnings.

### `outputs/reports/config_utilisee.yaml`

Copie exacte du fichier de configuration utilisé pour la résolution. Elle garantit la reproductibilité de l'exécution.

### `outputs/solutions/solution_formations.xlsx`

Export optionnel si `openpyxl` est disponible dans l'environnement. Il contient les onglets :

- `sessions` ;
- `communes_affectees` ;
- `statistiques` ;
- `validation` ;
- `configuration`.

Si la dépendance n'est pas disponible, les exports CSV, Markdown, JSON et YAML restent produits.

### `outputs/maps/solution_map.html`

Export HTML autonome de contrôle visuel et métier. Il est produit avec :

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml --export --map
```

Les données sont embarquées directement dans le fichier HTML sous forme de constantes JavaScript :

- `globalStats` ;
- `validationChecks` ;
- `points` ;
- `summary`.

La carte utilise du JavaScript natif et un SVG pour dessiner les communes, les pivots et les liaisons optionnelles commune -> pivot. Les points restent visibles même sans fond de carte externe. Les coordonnées latitude/longitude sont optionnelles : les communes sans coordonnées sont listées dans le panneau de contrôle et ne bloquent pas les autres exports.

## Alertes métier

Les alertes ne sont pas des violations de contraintes. Elles signalent des points à contrôler :

- session proche de la capacité maximale ;
- session faiblement remplie ;
- temps de trajet maximal proche de `T` ;
- session multi-territoires ;
- forte mixité TPC dans une session PC ;
- pivot avec coût d'éligibilité élevé ;
- population très dispersée ;
- commune affectée à un pivot d'un territoire différent.

## Exports d'assouplissement

La commande suivante produit les fichiers de suivi de la hiérarchie d'assouplissement :

```bash
cc-formation-optimizer solve-relaxed --config config/config_ear2027.yaml --export
```

Fichiers ajoutés :

- `outputs/reports/journal_assouplissements.json` : une entrée par tentative, avec paramètres modifiés et statuts ;
- `outputs/reports/rapport_assouplissements.md` : rapport lisible expliquant ce qui a été assoupli ;
- `outputs/reports/config_finale.yaml` : configuration finale retenue si une solution validée est trouvée.

En cas d'échec complet, le journal et le rapport sont quand même produits pour diagnostiquer le blocage. `config_finale.yaml` n'est produit que si une solution validée existe.
