# travel_time_core

Sous-projet independant pour produire des matrices de temps de trajet entre communes.

Il ne depend pas du package `cc_formation_optimizer` et ne doit pas etre importe par lui.
Le contrat entre les deux projets est uniquement un echange de fichiers CSV ou ODS documentes.

## Installation

Depuis le dossier `travel_time_core` :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

La console expose deux noms equivalents apres installation :

```powershell
travel-time-core --help
```

```powershell
travel-times --help
```

Sans installation editable, les tests restent lancables depuis la racine du depot avec :

```powershell
pytest travel_time_core/tests
```

## Configuration

La configuration autonome de reference est :

```text
travel_time_core/config/config_travel_times.yaml
```

Elle contient :

- les chemins d'entree ;
- les chemins de sortie ;
- le mapping des colonnes ;
- les seuils de matrices `60`, `75`, `90`, `120` ;
- le chemin du cache SQLite ;
- les parametres IGN/Geoplateforme ;
- le mode d'execution `offline` ou `ign` ;
- le garde-fou `runtime.allow_network`.

Par defaut, `runtime.mode` vaut `offline` et `runtime.allow_network` vaut `false`.
Aucun appel API n'est necessaire pour les tests ou pour le pipeline offline.

## Entree CSV recommandee

Le fichier communes configure doit contenir au minimum :

```text
code_commune,nom_commune,categorie,latitude,longitude
```

Colonnes optionnelles utiles :

```text
population,territoire_EAR
```

Les noms exacts sont configurables dans la section `columns`.

## Commandes principales

Depuis la racine du depot :

```powershell
travel-time-core --config travel_time_core/config/config_travel_times.yaml validate-config
```

```powershell
travel-time-core --config travel_time_core/config/config_travel_times.yaml import-communes
```

```powershell
travel-time-core --config travel_time_core/config/config_travel_times.yaml build-candidates
```

```powershell
travel-time-core --config travel_time_core/config/config_travel_times.yaml compute
```

```powershell
travel-time-core --config travel_time_core/config/config_travel_times.yaml export-matrices
```

```powershell
travel-time-core --config travel_time_core/config/config_travel_times.yaml run-pipeline
```

Les anciennes commandes restent disponibles pour les flux ODS/API existants :

```powershell
travel-times --config travel_time_core/config/config_travel_times.yaml validate-input --input travel_time_core/data/input/villes.ods
```

## Mode offline

Le mode offline utilise les coordonnees du CSV et un estimateur deterministe base sur la distance haversine.
Il sert aux tests, aux essais et aux pipelines sans reseau.

Parametres :

- `runtime.offline_speed_kmh` ;
- `runtime.offline_distance_factor` ;
- `runtime.max_couples`.

## Mode IGN / Geoplateforme

Les appels reseau sont isoles dans `src/travel_times/geocode.py` et `src/travel_times/ign_client.py`.
Pour autoriser le calcul via IGN, la configuration doit declarer explicitement :

```yaml
runtime:
  mode: "ign"
  allow_network: true
```

La cle API ne doit pas etre stockee en dur. Elle peut etre fournie par :

```powershell
$env:TRAVEL_TIMES_IGN_API_KEY="..."
```

## Cache et reprise

Les communes, candidats et temps calcules sont stockes dans SQLite :

```text
travel_time_core/data/cache/travel_times.sqlite
```

La commande `compute` ne recalcule pas les couples deja presents dans le cache, sauf avec `--refresh`.
Cela permet de reprendre un calcul interrompu.

## Sorties

Le dossier de sortie par defaut est :

```text
travel_time_core/data/output/
```

Sorties principales :

- `travel_times_sparse.csv` : table longue interne avec statuts, distances et durees ;
- `travel_times_matrix_minutes.csv` : matrice large complete ;
- `travel_times_matrix_minutes_max_60min.csv` ;
- `travel_times_matrix_minutes_max_75min.csv` ;
- `travel_times_matrix_minutes_max_90min.csv` ;
- `travel_times_matrix_minutes_max_120min.csv` ;
- `generation_report.json` : rapport de generation ;
- `temps_trajet_clean.csv` : export compatible avec `cc-formation-optimizer`.

## CSV compatible optimiseur

Le fichier compatible contient exactement :

```text
code_commune_origine,code_commune_pivot,temps_minutes
```

Il peut etre copie manuellement vers :

```text
data/processed/temps_trajet_clean.csv
```

Cette copie n'est pas automatisee afin de conserver l'independance entre les deux projets.

## Tests

Depuis la racine du depot :

```powershell
pytest travel_time_core/tests
```

Puis, pour verifier que le projet principal n'est pas impacte :

```powershell
pytest
```
