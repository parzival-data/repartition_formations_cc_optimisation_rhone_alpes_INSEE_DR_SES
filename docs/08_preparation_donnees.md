# Preparation des donnees reelles

## Commande

Depuis la racine du depot :

```bash
cc-formation-optimizer prepare-data --config config/config_ear2027.yaml --input-dir donnee_brut_EAR27 --output-dir data/processed --report
```

Options utiles :

- `--input-dir` : dossier des fichiers bruts, par exemple `donnee_brut_EAR27` ou `donnee_brut_EAR2027`.
- `--output-dir` : dossier des CSV propres, par defaut `data/processed`.
- `--report` : genere le rapport Markdown et les statistiques JSON.
- `--dry-run` : analyse sans ecrire de fichiers.
- `--strict` : echoue si une anomalie bloquante est detectee.

## Fichiers bruts observes

Le dossier brut inspecte contient :

- `info_minimum.ods` : communes, categories, territoires, population et logements.
- `villes_rhone_alpes.ods` : meme structure que `info_minimum.ods`.
- `matrice_temps_trajets_complete.ods` : matrice large des temps.
- `matrice_temps_trajets_max_60min.ods` : matrice large filtree.
- `matrice_temps_trajets_max_90min.ods` : matrice large filtree utilisee par defaut avec `T=90`.
- `matrice_temps_trajets_max_120min.ods` : matrice large filtree.
- `cities_geocoded.ods` : coordonnees latitude/longitude des communes.

Aucun fichier de compatibilites n'a ete detecte. Cette absence n'est pas
bloquante : le modele interprete les compatibilites absentes comme `b_ij = 1`.

## Mapping YAML

La section `data_preparation` de `config/config_ear2027.yaml` documente les
colonnes brutes et les sorties :

- `communes.file` et `communes.sheet` selectionnent la source des communes.
- `communes.columns` mappe les noms bruts vers les champs propres.
- `communes.category_mapping` convertit les categories brutes vers `PC` ou `TPC`.
- `travel_times.file` et `travel_times.sheet` selectionnent la matrice de temps.
- `coordinates.file` et `coordinates.sheet` selectionnent le fichier de coordonnees.
- `coordinates.columns` mappe le code commune, la latitude, la longitude et le nom informatif.
- `compatibilities.file` peut etre renseigne si un fichier de compatibilites est ajoute.

Les noms de colonnes brutes peuvent changer tant que le mapping YAML est mis a
jour et que les transformations restent documentees.

Si `coordinates.file` n'est pas renseigne, le workflow cherche d'abord
`cities_geocoded.ods`, puis les fichiers dont le nom contient `geocod` ou
`coord`. Cette detection automatique est une aide ; le YAML reste la source de
verite recommandee pour un jeu de donnees reel.

## Coordonnees

Le fichier de coordonnees actuel contient les colonnes :

- `insee_code` : code commune utilise pour la jointure ;
- `name` : nom de commune informatif ;
- `lat` : latitude ;
- `lon` : longitude ;
- `coord_source`, `geocode_status` et autres colonnes de controle ignorees par le solveur.

La jointure est faite apres nettoyage des communes, sur le code commune
normalise. Les controles appliques sont :

- code commune non vide ;
- unicite des codes dans le fichier de coordonnees ;
- latitude et longitude numeriques ;
- latitude comprise entre `-90` et `90` ;
- longitude comprise entre `-180` et `180` ;
- signalement des coordonnees hors perimetre EAR2027.

Le fichier source ne declare pas explicitement de systeme de coordonnees. Les
colonnes `lat`/`lon` sont conservees sans conversion. Une conversion ne doit
etre ajoutee que si le systeme source est documente.

## Sorties

La preparation produit :

- `data/processed/communes_clean.csv` ;
- `data/processed/temps_trajet_clean.csv` ;
- `data/processed/compatibilites_clean.csv` si une source de compatibilites existe ;
- `outputs/reports/rapport_preparation_donnees.md` avec `--report` ;
- `outputs/reports/statistiques_preparation_donnees.json` avec `--report`.

Le rapport indique les fichiers lus, les colonnes renommees, les colonnes
ignorees, les volumes, les anomalies et les transformations realisees. Il
inclut aussi le fichier de coordonnees utilise, les colonnes de jointure, le
nombre de coordonnees lues, valides, invalides, hors perimetre et les communes
encore sans coordonnees.

## Controles

Anomalies bloquantes :

- code commune vide ;
- doublon de commune ;
- categorie inconnue ;
- population ou logements non numeriques ou negatifs ;
- latitude ou longitude non numerique ;
- latitude ou longitude hors plage ;
- doublon de code commune dans le fichier de coordonnees ;
- origine ou pivot de trajet vide ;
- origine ou pivot absent du fichier communes ;
- temps de trajet non numerique ou negatif ;
- doublon origine-pivot ;
- compatibilite differente de `0` ou `1`.

Anomalies non bloquantes :

- colonnes latitude/longitude absentes ;
- communes sans coordonnees ;
- coordonnees hors perimetre EAR2027 ;
- fichier de compatibilites absent ;
- matrice de trajets asymetrique ;
- trajets absents.

Les trajets absents ne sont pas completes. Le solveur les traite comme
interdits.

## Diagnostic

Apres preparation, verifier la chaine sans resolution longue :

```bash
cc-formation-optimizer diagnose --config config/config_ear2027.yaml
```

Le diagnostic affiche les volumes de communes PC/TPC, le total de CC, la borne
minimale `ceil(total_CC / Q)`, le nombre de slots, les trajets admissibles, les
communes orphelines, les PC sans pivot compatible PC, la coherence `B=f+k` et
la disponibilite des coordonnees pour la carte.
