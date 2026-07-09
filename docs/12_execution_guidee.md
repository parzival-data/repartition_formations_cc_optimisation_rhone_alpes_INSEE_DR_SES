# Exécution guidée

La commande `guided-run` accompagne un utilisateur non expert dans le pipeline
complet du projet. Elle affiche les dossiers utilisés, vérifie les fichiers,
propose les étapes une par une et demande confirmation avant les traitements
longs.

Commande principale :

```powershell
cc-formation-optimizer guided-run --config config/config_ear2027.yaml
```

## Dossiers utilisés

Par défaut, la commande utilise :

- `donnee_brut_EAR27/` pour les fichiers bruts ;
- `data/processed/` pour les CSV propres ;
- `outputs/` pour les exports finaux.

Ces dossiers peuvent être remplacés :

```powershell
cc-formation-optimizer guided-run --config config/config_ear2027.yaml --input-dir donnee_brut_EAR27 --processed-dir data/processed --output-dir outputs
```

## Fichiers à déposer

Pour la configuration actuelle, les fichiers bruts attendus sont décrits dans
`config/config_ear2027.yaml`, section `data_preparation`.

Le fichier communes sert à produire :

```text
data/processed/communes_clean.csv
```

Le fichier de temps de trajet importé ou généré sert à produire :

```text
data/processed/temps_trajet_clean.csv
```

Les coordonnées sont utiles pour la carte, mais elles ne sont pas une contrainte
du modèle CP-SAT.

## Étapes exécutées

La commande guide les étapes suivantes :

1. vérification de l'environnement et des chemins ;
2. préparation des données avec `prepare-data`, si demandée ;
3. vérification et correction des diagonales `i -> i` dans la matrice de temps ;
4. réutilisation ou recalcul des temps avec `travel_time_core` ;
5. diagnostic avant optimisation ;
6. optimisation normale, puis proposition de `solve-relaxed` si nécessaire ;
7. vérification des exports et de la carte ;
8. proposition de la surcouche métier post-optimisation.

La correction des diagonales ajoute les lignes manquantes avec un temps `0` et
peut corriger les diagonales présentes avec un temps non nul. Un rapport est
écrit dans :

```text
outputs/reports/rapport_diagonale_temps_trajet.json
```

## Réponses aux confirmations

Quand la commande affiche une question avec `[O/n]` ou `[o/N]`, la lettre en
majuscule indique la réponse par défaut si l'utilisateur appuie simplement sur
`Entrée`.

```text
[O/n]
```

signifie que `Oui` est la réponse par défaut :

- `Entrée` : oui ;
- `o`, `oui`, `y` ou `yes` : oui ;
- `n` ou `non` : non.

```text
[o/N]
```

signifie que `Non` est la réponse par défaut :

- `Entrée` : non ;
- `o`, `oui`, `y` ou `yes` : oui ;
- `n` ou `non` : non.

Les étapes longues ou importantes, comme le calcul des temps de trajet ou le
solveur, utilisent généralement `[o/N]` pour éviter un lancement involontaire.

## Temps de trajet

Le calcul des temps reste porté par le sous-projet indépendant
`travel_time_core/`. La commande guidée ne duplique pas sa logique. Elle peut
lancer la commande existante :

```powershell
travel-time-core --config travel_time_core/config/config_travel_times.yaml run-pipeline
```

Quand le CSV compatible existe, il peut être copié vers :

```text
data/processed/temps_trajet_clean.csv
```

## Optimisation

La commande demande confirmation avant de lancer le solveur. Elle explique le
statut obtenu :

- `OPTIMAL` : solution faisable et optimalité prouvée ;
- `FEASIBLE` : solution valide trouvée, mais optimalité non prouvée ;
- `INFEASIBLE` : aucune solution ne respecte les contraintes ;
- `UNKNOWN` : arrêt sans preuve suffisante ou sans solution exploitable.

Une solution `FEASIBLE` ne doit jamais être présentée comme optimale.

## Exports attendus

Après une optimisation avec exports et carte, vérifier :

```text
outputs/solutions/sessions.csv
outputs/solutions/communes_affectees.csv
outputs/reports/rapport_solution.md
outputs/reports/statistiques_solution.json
outputs/maps/solution_map.html
```

Si les exports existent déjà, la commande le signale et peut proposer de
régénérer seulement la carte.

## Surcouche métier

La dernière étape propose :

```powershell
cc-formation-optimizer postprocess-business-rules --config config/config_ear2027.yaml --input-dir outputs --output-dir outputs/postprocess --min-travel-time-gain-min 5
```

Cette étape ne modifie pas la solution optimisée. Elle écrit :

```text
outputs/postprocess/business_reallocation_proposals.csv
outputs/postprocess/business_reallocation_summary.csv
```

## Options utiles

```text
--yes
--skip-travel-times
--skip-solve
--skip-map
--skip-postprocess
--input-dir
--processed-dir
--output-dir
```

`--yes` confirme automatiquement les étapes courtes, mais les étapes longues
comme le calcul des temps ou le solveur demandent encore une confirmation.

## En cas d'erreur

Lire le message affiché : il indique normalement le fichier absent ou l'étape
qui bloque. Les cas les plus courants sont :

- fichier brut absent dans `donnee_brut_EAR27/` ;
- CSV préparé absent dans `data/processed/` ;
- colonne manquante dans un CSV ;
- temps de trajet manquant pour certaines communes ;
- diagnostic indiquant des communes sans trajet admissible.
