# Repartition des formations CC - EAR 2027

Ce depot contient le socle Python d'un outil d'optimisation pour organiser les sessions de formation des coordonnateurs communaux (CC) des communes PC/TPC pour l'EAR 2027.

Le modele cible est celui de la specification fournie : un seul seuil de trajet `T`, une capacite `Q`, des budgets `f`, `k`, `B` avec `B = f + k`, des slots `M_PC = 3` et `M_TPC = 1`, et une separation PC -> TPC stricte traitee comme contrainte dure dans le modele futur.

## Installation

```bash
python -m pip install -e ".[dev]"
```

## Commandes

Valider la configuration principale :

```bash
cc-formation-optimizer validate-config --config config/config_ear2027.yaml
```

Afficher un resume de configuration :

```bash
cc-formation-optimizer show-config --config config/config_ear2027.yaml
```

Preparer les donnees reelles :

```bash
cc-formation-optimizer prepare-data --config config/config_ear2027.yaml --input-dir donnee_brut_EAR27 --output-dir data/processed --report
```

Cette commande lit les fichiers bruts `.ods`, applique les mappings declares
dans `config/config_ear2027.yaml`, produit les CSV propres dans
`data/processed/` et genere un rapport dans `outputs/reports/`. Utiliser
`--dry-run` pour analyser sans ecrire et `--strict` pour echouer en presence
d'anomalies bloquantes.

Le fichier de coordonnees `cities_geocoded.ods` est joint aux communes par code
INSEE normalise. Les coordonnees sont utiles a la carte HTML, mais elles ne
modifient pas l'optimisation ; une commune sans coordonnees reste affectee et
apparait dans les exports non cartographiques.

Verifier les donnees preparees sans lancer de resolution longue :

```bash
cc-formation-optimizer diagnose --config config/config_ear2027.yaml
```

Construire et resoudre le modele CP-SAT minimal :

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml
```

Cette commande charge les CSV configures, construit les parametres derives, genere le modele CP-SAT, lance le solveur, extrait la solution metier et lance la validation automatique. Elle affiche le statut, l'objectif total recalcule, le nombre de sessions ouvertes, le nombre de communes affectees, le total de CC et le resultat de validation.

Produire les exports finaux apres validation :

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml --export
```

Les fichiers sont crees dans `outputs/solutions/` et `outputs/reports/`. Aucun export exploitable n'est produit si la validation echoue.

Produire aussi la carte HTML autonome :

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml --export --map
```

La carte est creee dans `outputs/maps/solution_map.html`. Elle embarque les donnees de controle dans le HTML et reste un export optionnel : si les coordonnees latitude/longitude sont absentes, elle indique les communes non cartographiees sans bloquer les exports classiques.

Regenerer uniquement la carte depuis des exports existants, sans relancer le solveur :

```bash
cc-formation-optimizer render-map --config config/config_ear2027.yaml --solution-dir outputs
```

Cette commande lit `outputs/solutions/sessions.csv`,
`outputs/solutions/communes_affectees.csv` et
`outputs/reports/statistiques_solution.json`, recharge les communes propres
configurees pour les coordonnees, puis reecrit
`outputs/maps/solution_map.html`. Elle est destinee au debogage cartographique
quand la solution d'optimisation existe deja.

Resoudre avec assouplissement hierarchique :

```bash
cc-formation-optimizer solve-relaxed --config config/config_ear2027.yaml --export --map
```

`solve` utilise strictement la configuration fournie. `solve-relaxed` teste d'abord cette configuration, puis applique les niveaux d'assouplissement configures jusqu'a trouver une solution validee. Chaque tentative est journalisee dans `outputs/reports/journal_assouplissements.json`, avec un rapport lisible dans `outputs/reports/rapport_assouplissements.md` et une copie de la configuration finale dans `outputs/reports/config_finale.yaml` si une solution est retenue.

La contrainte stricte PC vers session TPC n'est jamais relachee automatiquement.

## Depannage de la carte

Si le fond de carte ne s'affiche pas, verifier l'acces reseau a
`https://data.geopf.fr/wmts` et les requetes navigateur vers `data.geopf.fr`.
Les points doivent rester visibles meme si le fond WMTS echoue.

Si les points semblent mal places, verifier que `latitude` vient de `lat` et
`longitude` de `lon`. Pour Auvergne-Rhone-Alpes, les latitudes attendues sont
autour de 44 a 47 et les longitudes autour de 2 a 7. Le panneau repliable
"Debug carte" dans le HTML affiche les bounds, le centre initial, le zoom
initial, le nombre de points avec coordonnees et les erreurs de tuiles.

## Organisation

- `config/` : configuration YAML et schema documentaire.
- `data/` : donnees brutes, donnees transformees et echantillons. Les donnees brutes et preparees reelles sont ignorees par Git.
- `docs/` : documentation Markdown de la modelisation et du projet.
- `src/cc_formation_optimizer/` : package Python.
- `tests/` : tests automatises et fixtures.
- `outputs/` : sorties generees par les futures executions.
