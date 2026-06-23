# Donnees d'entree

## Communes

Le fichier des communes doit contenir au minimum :

- un identifiant de commune ;
- un nom de commune ;
- une population ;
- une categorie metier `PC` ou `TPC`.

Le nombre de CC a former est derive de la population :

- `q_i = 1` si `population(i) <= 5000` ;
- `q_i = 2` si `population(i) > 5000`.

Le seuil `5000` est configure dans `config/config_ear2027.yaml`.

## Temps de trajet

Le fichier des trajets contient des lignes origine-destination avec un temps en minutes. La matrice est consideree comme potentiellement asymetrique.

Le modele utilise un seul parametre de temps maximal `T`. Une liaison est admissible si `tau_ij <= T`. Une absence de trajet dans la matrice est interpretee comme une liaison interdite.

## Compatibilites

Le fichier de compatibilite permet d'imposer `b_ij = 0` pour des regroupements juges incoherents. En l'absence de fichier ou de ligne specifique, la compatibilite par defaut sera `1`.
