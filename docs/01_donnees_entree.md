# Donnees d'entree

## Workflow recommande

Les donnees reelles ne sont pas chargees directement par le solveur. Elles
sont d'abord preparees depuis le dossier brut `donnee_brut_EAR27/` avec :

```bash
cc-formation-optimizer prepare-data --config config/config_ear2027.yaml --input-dir donnee_brut_EAR27 --output-dir data/processed --report
```

Le depot peut aussi accepter un dossier nomme `donnee_brut_EAR2027/` via
`--input-dir`. Les fichiers propres produits sont :

- `data/processed/communes_clean.csv` ;
- `data/processed/temps_trajet_clean.csv` ;
- `data/processed/compatibilites_clean.csv` seulement si un fichier brut de compatibilites existe.

Les donnees brutes et les fichiers prepares ne sont pas versionnes. Les
fixtures sous `tests/fixtures/` restent versionnees.

## Communes

Le fichier des communes doit contenir au minimum :

- un identifiant de commune ;
- un nom de commune ;
- une population ;
- une categorie metier `PC` ou `TPC`.

Le fichier propre attendu par le solveur contient les colonnes :

- `code_commune` ;
- `nom_commune` ;
- `categorie` ;
- `territoire_EAR` ;
- `population` ;
- `logements` ;
- `latitude` ;
- `longitude`.

Le nombre de CC a former est derive de la population :

- `q_i = 1` si `population(i) <= 5000` ;
- `q_i = 2` si `population(i) > 5000`.

Le seuil `5000` est configure dans `config/config_ear2027.yaml`.

## Temps de trajet

Le fichier des trajets contient des lignes origine-destination avec un temps en minutes. La matrice est consideree comme potentiellement asymetrique.

Le modele utilise un seul parametre de temps maximal `T`. Une liaison est admissible si `tau_ij <= T`. Une absence de trajet dans la matrice est interpretee comme une liaison interdite.

Le fichier propre attendu contient :

- `code_commune_origine` ;
- `code_commune_pivot` ;
- `temps_minutes`.

Les trajets absents dans les matrices brutes ne sont jamais completes
artificiellement.

## Compatibilites

Le fichier de compatibilite permet d'imposer `b_ij = 0` pour des regroupements juges incoherents. En l'absence de fichier ou de ligne specifique, la compatibilite par defaut sera `1`.

Si aucun fichier de compatibilites n'est detecte pendant la preparation, la
preparation continue et le modele garde `b_ij = 1` par defaut.
