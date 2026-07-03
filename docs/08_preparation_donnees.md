# Préparation des données réelles

## Commande

Depuis la racine du dépôt :

```bash
cc-formation-optimizer prepare-data --config config/config_ear2027.yaml --input-dir donnee_brut_EAR27 --output-dir data/processed --report
```

Options utiles :

- `--input-dir` : dossier des fichiers bruts, par exemple `donnee_brut_EAR27` ou `donnee_brut_EAR2027`.
- `--output-dir` : dossier des CSV propres, par défaut `data/processed`.
- `--report` : généré le rapport Markdown et les statistiques JSON.
- `--dry-run` : analyse sans écrire de fichiers.
- `--strict` : échoue si une anomalie bloquante est détectee.

## Fichiers bruts observes

Le dossier brut inspecte contient :

- `info_minimum.ods` : communes, catégories, territoires, population et logements.
- `villes_rhone_alpes.ods` : même structuré que `info_minimum.ods`.
- `matrice_temps_trajets_complete.ods` : matrice large des temps.
- `matrice_temps_trajets_max_60min.ods` : matrice large filtrée.
- `matrice_temps_trajets_max_90min.ods` : matrice large filtrée configurée comme source brute. Le seuil dur courant du modèle reste `T=60` et est appliqué ensuite lors de la construction de `a_ij`.
- `matrice_temps_trajets_max_120min.ods` : matrice large filtrée.
- `cities_geocoded.ods` : coordonnées latitude/longitude des communes.

Aucun fichier de compatibilités n'a été détecté. Cette absence n'est pas
bloquante : le modèle interprété les compatibilités absentes comme `b_ij = 1`.

## Mapping YAML

La section `data_preparation` de `config/config_ear2027.yaml` documente les
colonnes brutes et les sorties :

- `communes.file` et `communes.sheet` selectionnent la source des communes.
- `communes.columns` mappe les noms bruts vers les champs propres.
- `communes.category_mapping` convertit les catégories brutes vers `PC` ou `TPC`.
- `travel_times.file` et `travel_times.sheet` selectionnent la matrice de temps.
- `coordinates.file` et `coordinates.sheet` selectionnent le fichier de coordonnées.
- `coordinates.columns` mappe le code commune, la latitude, la longitude et le nom informatif.
- `compatibilities.file` peut être renseigné si un fichier de compatibilités est ajouté.

Les noms de colonnes brutes peuvent changer tant que le mapping YAML est mis à
jour et que les transformations restent documentées.

Si `coordinates.file` n'est pas renseigné, le workflow cherche d'abord
`cities_geocoded.ods`, puis les fichiers dont le nom contient `geocod` ou
`coord`. Cette détection automatique est une aide ; le YAML reste la source de
vérité recommandée pour un jeu de données réel.

## Coordonnées

Le fichier de coordonnées actuel contient les colonnes :

- `insee_code` : code commune utilisé pour la jointure ;
- `name` : nom de commune informatif ;
- `lat` : latitude ;
- `lon` : longitude ;
- `coord_source`, `geocode_status` et autres colonnes de contrôle ignorées par le solveur.

La jointure est faite après nettoyage des communes, sur le code commune
normalisé. Les contrôles appliques sont :

- code commune non vide ;
- unicite des codes dans le fichier de coordonnées ;
- latitude et longitude numériques ;
- latitude comprise entre `-90` et `90` ;
- longitude comprise entre `-180` et `180` ;
- signalement des coordonnées hors périmètre EAR2027.

Le fichier source ne déclaré pas explicitement de système de coordonnées. Les
colonnes `lat`/`lon` sont conservées sans conversion. Une conversion ne doit
être ajoutée que si le système source est documenté.

## Sorties

La préparation produit :

- `data/processed/communes_clean.csv` ;
- `data/processed/temps_trajet_clean.csv` ;
- `data/processed/compatibilites_clean.csv` si une source de compatibilités existe ;
- `outputs/reports/rapport_preparation_donnees.md` avec `--report` ;
- `outputs/reports/statistiques_preparation_donnees.json` avec `--report`.

Le rapport indique les fichiers lus, les colonnes renommées, les colonnes
ignorées, les volumes, les anomalies et les transformations réalisées. Il
inclut aussi le fichier de coordonnées utilisé, les colonnes de jointure, le
nombre de coordonnées lues, valides, invalides, hors périmètre et les communes
encore sans coordonnées.

## Contrôles

Anomalies bloquantes :

- code commune vide ;
- doublon de commune ;
- catégorie inconnue ;
- population ou logements non numériques ou negatifs ;
- latitude ou longitude non numerique ;
- latitude ou longitude hors plage ;
- doublon de code commune dans le fichier de coordonnées ;
- origine ou pivot de trajet vide ;
- origine ou pivot absent du fichier communes ;
- temps de trajet non numerique ou negatif ;
- doublon origine-pivot ;
- compatibilité différente de `0` ou `1`.

Anomalies non bloquantes :

- colonnes latitude/longitude absentes ;
- communes sans coordonnées ;
- coordonnées hors périmètre EAR2027 ;
- fichier de compatibilités absent ;
- matrice de trajets asymétrique ;
- trajets absents.

Les trajets absents ne sont pas complétés. Le solveur les traité comme
interdits.

## Diagnostic

Après préparation, vérifier la chaîne sans résolution longue :

```bash
cc-formation-optimizer diagnose --config config/config_ear2027.yaml
```

Le diagnostic affiche les volumes de communes PC/TPC, le total de CC, la borne
minimale `ceil(total_CC / Q)`, le nombre de slots, les trajets admissibles, les
communes orphelines, les PC sans pivot compatible PC, la cohérence `B=f+k` et
la disponibilité des coordonnées pour la carte.
