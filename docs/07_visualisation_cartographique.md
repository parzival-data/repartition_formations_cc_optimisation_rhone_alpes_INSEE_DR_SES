# Visualisation cartographique

La visualisation cartographique est un export HTML autonome produit apres extraction et validation de la solution.

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml --export --map
```

Le fichier genere est :

```text
outputs/maps/solution_map.html
```

## Role

La carte sert au controle visuel et metier :

- verifier les affectations commune -> pivot ;
- reperer les temps de trajet proches de `T` ;
- identifier les sessions mixtes ou multi-territoires ;
- parcourir les controles du modele ;
- consulter les tableaux de sessions et de communes.

La solution officielle reste celle des exports valides : CSV, rapport Markdown, JSON de statistiques et configuration utilisee.

## Donnees embarquees

Le HTML embarque directement les donnees suivantes :

- `globalStats` : statistiques globales ;
- `validationChecks` : controles issus de `validate_solution()` ;
- `points` : communes cartographiees ;
- `summary` : synthese des sessions.

Aucune bibliotheque JavaScript externe n'est requise. Le rendu des points est fait en SVG avec du JavaScript natif.

## Coordonnees

La carte depend des champs optionnels `latitude` et `longitude` dans les donnees communes. Si une commune n'a pas de coordonnees :

- elle n'est pas affichee sur la carte ;
- elle est listee dans le panneau "communes sans coordonnees" ;
- le compteur `communes_sans_coordonnees` est renseigne dans `globalStats`.

Si aucune commune n'a de coordonnees, le HTML est tout de meme produit avec un message clair et les controles metier restent consultables.

## Fond de carte

Le HTML est autonome et les points restent visibles sans fond externe. Un fond IGN/Geoplateforme pourra etre ajoute ou active ulterieurement si l'environnement d'utilisation autorise l'acces reseau, par exemple via les tuiles WMTS `https://data.geopf.fr/wmts`.

## Limites

- La carte est un export de controle, pas une source de verite.
- Les alertes affichees sont non bloquantes.
- Les donnees reelles et les coordonnees definitives seront integrees a la fin du developpement.
