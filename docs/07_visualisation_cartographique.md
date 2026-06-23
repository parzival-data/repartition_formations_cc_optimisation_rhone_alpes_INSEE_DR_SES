# Visualisation cartographique

La visualisation cartographique est un export HTML autonome produit apres extraction et validation de la solution.

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml --export --map
```

Regenerer uniquement la carte depuis des exports existants, sans relancer le
solveur :

```bash
cc-formation-optimizer render-map --config config/config_ear2027.yaml --solution-dir outputs
```

La commande lit `solutions/sessions.csv`, `solutions/communes_affectees.csv` et
`reports/statistiques_solution.json` dans le dossier indique, recharge les
communes propres configurees pour joindre les coordonnees, puis produit
`maps/solution_map.html`.

Le fichier genere est :

```text
outputs/maps/solution_map.html
```

## Role

La carte sert au controle visuel et metier :

- verifier les affectations commune -> pivot ;
- reperer les temps de trajet proches de `T` ;
- identifier les sessions mixtes ou multi-territoires ;
- afficher uniquement les communes pivots qui accueillent au moins une session ;
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

Les coordonnees sont ajoutees pendant la preparation des donnees, par jointure
entre les communes et le fichier configure dans `data_preparation.coordinates`
du YAML. Le fichier actuel est `cities_geocoded.ods` avec les colonnes
`insee_code`, `lat` et `lon`. Elles ne changent pas le modele d'optimisation :
elles servent uniquement a positionner les points dans l'export HTML.

## Fond de carte

Le HTML est autonome et les points restent visibles sans fond externe. Le fond
IGN/Geoplateforme est charge via les tuiles WMTS `https://data.geopf.fr/wmts`
avec `LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2` et `TILEMATRIXSET=PM`.

Les points et les tuiles utilisent la meme projection Web Mercator. Les
coordonnees restent exprimees en longitude/latitude WGS84 dans les donnees
embarquees, puis sont projetees cote navigateur.

Un panneau repliable "Debug carte" indique le nombre de points, les bounds
latitude/longitude, le centre, le zoom initial et le nombre de tuiles tentees.

## Depannage de la carte

Si le fond de carte ne s'affiche pas :

- verifier l'acces reseau a `https://data.geopf.fr/wmts` ;
- verifier dans la console navigateur les requetes vers `data.geopf.fr` ;
- le message "Fond de carte non charge. Verifier l'acces reseau a data.geopf.fr." indique que les tuiles n'ont pas charge ;
- les points doivent rester visibles meme sans fond de carte.

Si les points semblent mal places :

- verifier que `latitude` vient de la colonne `lat` et `longitude` de `lon` ;
- verifier que les latitudes sont autour de 44 a 47 et les longitudes autour de 2 a 7 pour Auvergne-Rhone-Alpes ;
- si ces ordres de grandeur sont inverses, les colonnes latitude/longitude sont probablement inversees ;
- verifier les valeurs `minLat`, `maxLat`, `minLon`, `maxLon`, le centre et le zoom dans le panneau "Debug carte".

Si la carte semble vide :

- verifier que `points_avec_coordonnees` est non nul dans le panneau debug ;
- verifier que `const points` contient des nombres JSON pour `lat` et `lon`, pas des chaines ;
- regenerer uniquement la carte avec `render-map` pour eviter une nouvelle resolution longue.

## Limites

- La carte est un export de controle, pas une source de verite.
- Les alertes affichees sont non bloquantes.
- Le fond de carte depend d'un acces reseau au service WMTS externe.
