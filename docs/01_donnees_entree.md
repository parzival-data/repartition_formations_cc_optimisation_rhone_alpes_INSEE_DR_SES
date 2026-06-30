# Données d'entrée

## Workflow recommandé

Les données réelles ne sont pas chargées directement par le solveur. Elles
sont d'abord préparées depuis le dossier brut `donnee_brut_EAR27/` avec :

```bash
cc-formation-optimizer prepare-data --config config/config_ear2027.yaml --input-dir donnee_brut_EAR27 --output-dir data/processed --report
```

Le dépôt peut aussi accepter un dossier nommé `donnee_brut_EAR2027/` via
`--input-dir`. Les fichiers propres produits sont :

- `data/processed/communes_clean.csv` ;
- `data/processed/temps_trajet_clean.csv` ;
- `data/processed/compatibilites_clean.csv` seulement si un fichier brut de compatibilités existe.

Les données brutes et les fichiers préparés ne sont pas versionnés. Les
fixtures sous `tests/fixtures/` restent versionnées.

## Communes

Le fichier des communes doit contenir au minimum :

- un identifiant de commune ;
- un nom de commune ;
- une population ;
- une catégorie métier `PC` ou `TPC`.

Le fichier propre attendu par le solveur contient les colonnes :

- `code_commune` ;
- `nom_commune` ;
- `categorie` ;
- `territoire_EAR` ;
- `population` ;
- `logements` ;
- `latitude` ;
- `longitude`.

Le nombre de CC à former est dérivé de la population :

- `q_i = 1` si `population(i) <= 5000` ;
- `q_i = 2` si `population(i) > 5000`.

Le seuil `5000` est configuré dans `config/config_ear2027.yaml`.

## Temps de trajet

Le fichier des trajets contient des lignes origine-destination avec un temps en minutes. La matrice est considérée comme potentiellement asymétrique.

Le modèle utilise un seul paramètre de temps maximal `T`. Une liaison est admissible si `tau_ij <= T`. Une absence de trajet dans la matrice est interprétée comme une liaison interdite.

Le fichier propre attendu contient :

- `code_commune_origine` ;
- `code_commune_pivot` ;
- `temps_minutes`.

Les trajets absents dans les matrices brutes ne sont jamais complétés
artificiellement.

## Coordonnées

Un fichier de coordonnées peut être fourni dans le dossier brut. La
configuration actuelle utilise `cities_geocoded.ods`, feuille `cities`, avec :

- `insee_code` pour le code commune ;
- `lat` pour la latitude ;
- `lon` pour la longitude ;
- `name` comme nom de commune informatif si disponible.

La jointure se fait sur le code commune normalisé. Les coordonnées doivent être
des latitudes/longitudes numériques dans les plages `-90..90` et `-180..180`.
Si le système de coordonnées n'est pas précisé par le fichier source, aucune
conversion n'est tentée automatiquement.

Les coordonnées sont optionnelles pour l'optimisation. Elles sont nécessaires
pour afficher les communes sur la carte ; les communes sans coordonnées restent
dans les exports et dans la solution, mais ne sont pas dessinées sur la carte.

## Compatibilités

Le fichier de compatibilité permet d'imposer `b_ij = 0` pour des regroupements jugés incohérents. En l'absence de fichier ou de ligne spécifique, la compatibilité par défaut sera `1`.

Si aucun fichier de compatibilités n'est détecté pendant la préparation, la
préparation continue et le modèle garde `b_ij = 1` par défaut.
