# Execution guidee

La commande `guided-run` accompagne un utilisateur non expert dans le pipeline
complet du projet. Elle affiche les dossiers utilises, verifie les fichiers,
propose les etapes une par une et demande confirmation avant les traitements
longs.

Commande principale :

```powershell
cc-formation-optimizer guided-run --config config/config_ear2027.yaml
```

## Dossiers utilises

Par defaut, la commande utilise :

- `donnee_brut_EAR27/` pour les fichiers bruts ;
- `data/processed/` pour les CSV propres ;
- `outputs/` pour les exports finaux.

Ces dossiers peuvent etre remplaces :

```powershell
cc-formation-optimizer guided-run --config config/config_ear2027.yaml --input-dir donnee_brut_EAR27 --processed-dir data/processed --output-dir outputs
```

## Fichiers a deposer

Pour la configuration actuelle, les fichiers bruts attendus sont decrits dans
`config/config_ear2027.yaml`, section `data_preparation`.

Le fichier communes sert a produire :

```text
data/processed/communes_clean.csv
```

Le fichier de temps de trajet importe ou genere sert a produire :

```text
data/processed/temps_trajet_clean.csv
```

Les coordonnees sont utiles pour la carte, mais elles ne sont pas une contrainte
du modele CP-SAT.

## Etapes executees

La commande guide les etapes suivantes :

1. verification de l'environnement et des chemins ;
2. preparation des donnees avec `prepare-data`, si demandee ;
3. verification et correction des diagonales `i -> i` dans la matrice de temps ;
4. reutilisation ou recalcul des temps avec `travel_time_core` ;
5. diagnostic avant optimisation ;
6. optimisation normale, puis proposition de `solve-relaxed` si necessaire ;
7. verification des exports et de la carte ;
8. proposition de la surcouche metier post-optimisation.

La correction des diagonales ajoute les lignes manquantes avec un temps `0` et
peut corriger les diagonales presentes avec un temps non nul. Un rapport est
ecrit dans :

```text
outputs/reports/rapport_diagonale_temps_trajet.json
```

## Temps de trajet

Le calcul des temps reste porte par le sous-projet independant
`travel_time_core/`. La commande guidee ne duplique pas sa logique. Elle peut
lancer la commande existante :

```powershell
travel-time-core --config travel_time_core/config/config_travel_times.yaml run-pipeline
```

Quand le CSV compatible existe, il peut etre copie vers :

```text
data/processed/temps_trajet_clean.csv
```

## Optimisation

La commande demande confirmation avant de lancer le solveur. Elle explique le
statut obtenu :

- `OPTIMAL` : solution faisable et optimalite prouvee ;
- `FEASIBLE` : solution valide trouvee, mais optimalite non prouvee ;
- `INFEASIBLE` : aucune solution ne respecte les contraintes ;
- `UNKNOWN` : arret sans preuve suffisante ou sans solution exploitable.

Une solution `FEASIBLE` ne doit jamais etre presentee comme optimale.

## Exports attendus

Apres une optimisation avec exports et carte, verifier :

```text
outputs/solutions/sessions.csv
outputs/solutions/communes_affectees.csv
outputs/reports/rapport_solution.md
outputs/reports/statistiques_solution.json
outputs/maps/solution_map.html
```

Si les exports existent deja, la commande le signale et peut proposer de
regenerer seulement la carte.

## Surcouche metier

La derniere etape propose :

```powershell
cc-formation-optimizer postprocess-business-rules --config config/config_ear2027.yaml --input-dir outputs --output-dir outputs/postprocess --min-travel-time-gain-min 5
```

Cette etape ne modifie pas la solution optimisee. Elle ecrit :

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

`--yes` confirme automatiquement les etapes courtes, mais les etapes longues
comme le calcul des temps ou le solveur demandent encore une confirmation.

## En cas d'erreur

Lire le message affiche : il indique normalement le fichier absent ou l'etape
qui bloque. Les cas les plus courants sont :

- fichier brut absent dans `donnee_brut_EAR27/` ;
- CSV prepare absent dans `data/processed/` ;
- colonne manquante dans un CSV ;
- temps de trajet manquant pour certaines communes ;
- diagnostic indiquant des communes sans trajet admissible.
