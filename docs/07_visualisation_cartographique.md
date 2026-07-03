# Visualisation cartographique

La visualisation cartographique est un export HTML autonome produit après extraction et validation de la solution.

```bash
cc-formation-optimizer solve --config config/config_ear2027.yaml --export --map
```

Régénérer uniquement la carte depuis des exports existants, sans relancer le
solveur :

```bash
cc-formation-optimizer render-map --config config/config_ear2027.yaml --solution-dir outputs
```

La commande lit `solutions/sessions.csv`, `solutions/communes_affectees.csv` et
`reports/statistiques_solution.json` dans le dossier indiqué, rechargé les
communes propres configurées pour joindre les coordonnées, puis produit
`maps/solution_map.html`.

Le fichier généré est :

```text
outputs/maps/solution_map.html
```

## Rôle

La carte sert au contrôle visuel et métier :

- vérifier les affectations commune -> pivot ;
- reperer les temps de trajet proches de `T` ;
- identifier les sessions mixtes ou multi-territoires ;
- afficher uniquement les communes pivots qui accueillent au moins une session ;
- parcourir les contrôles du modèle ;
- consulter les tableaux de sessions et de communes.

La solution officielle reste celle des exports valides : CSV, rapport Markdown, JSON de statistiques et configuration utilisée.

## Legende

La page HTML contient une legende visible dans le panneau de contrôle.

Les formes des points indiquent la catégorie de la commune :

- cercle : commune PC ;
- carre : commune TPC.

La taille du symbole indique le rôle cartographique :

- taille normale : commune affectée à une session ;
- symbole plus gros : commune pivot d'au moins une session ouverte.

La couleur du point correspond à la session ou au groupe de formation. Comme
la palette est générée automatiquement, deux sessions peuvent avoir des
couleurs proches lorsque beaucoup de sessions sont affichées.

Le contour indique le niveau d'alerte :

- `OK` : aucune alerte détectee ;
- `warning` : point ou session à vérifier par les experts métier, sans violation
  bloquante des contraintes ;
- `error` : anomalie forte ou incohérence détectee dans les contrôles affiches,
  si ce niveau est présent dans les données embarquées.

Les lignes commune -> pivot sont facultatives. Elles sont masquees par défaut
et peuvent être affichées avec le filtre "Afficher les liaisons commune ->
pivot". Lorsque le filtre "Afficher les pivots seulement" est actif, les
liaisons sont masquees pour garder une lecture claire.

## Données embarquées

Le HTML embarque directement les données suivantes :

- `globalStats` : statistiques globales ;
- `validationChecks` : contrôles issus de `validate_solution()` ;
- `points` : communes cartographiees ;
- `summary` : synthèse des sessions.

Aucune bibliotheque JavaScript externe n'est requise. Le rendu des points est fait en SVG avec du JavaScript natif.

## Coordonnées

La carte dépend des champs optionnels `latitude` et `longitude` dans les données communes. Si une commune n'a pas de coordonnées :

- elle n'est pas affichée sur la carte ;
- elle est listée dans le panneau "communes sans coordonnées" ;
- le compteur `communes_sans_coordonnees` est renseigné dans `globalStats`.

Si aucune commune n'a de coordonnées, le HTML est tout de même produit avec un message clair et les contrôles métier restent consultables.

Les coordonnées sont ajoutées pendant la préparation des données, par jointure
entre les communes et le fichier configuré dans `data_preparation.coordinates`
du YAML. Le fichier actuel est `cities_geocoded.ods` avec les colonnes
`insee_code`, `lat` et `lon`. Elles ne changent pas le modèle d'optimisation :
elles servent uniquement à positionner les points dans l'export HTML.

## Fond de carte

Le HTML est autonome et les points restent visibles sans fond externe. Le fond
IGN/Geoplateforme est chargé via les tuiles WMTS `https://data.geopf.fr/wmts`
avec `LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2` et `TILEMATRIXSET=PM`.

Les points et les tuiles utilisent la même projection Web Mercator. Les
coordonnées restent exprimees en longitude/latitude WGS84 dans les données
embarquées, puis sont projetées côté navigateur.

Un panneau repliable "Debug carte" indique le nombre de points, les bounds
latitude/longitude, le centre, le zoom initial et le nombre de tuiles tentées.

## Depannage de la carte

Si le fond de carte ne s'affiche pas :

- vérifier l'accès réseau à `https://data.geopf.fr/wmts` ;
- vérifier dans la console navigateur les requétés vers `data.geopf.fr` ;
- le message "Fond de carte non chargé. Vérifier l'accès réseau à data.geopf.fr." indique que les tuiles n'ont pas chargé ;
- les points doivent rester visibles même sans fond de carte.

Si les points semblent mal places :

- vérifier que `latitude` vient de la colonne `lat` et `longitude` de `lon` ;
- vérifier que les latitudes sont autour de 44 à 47 et les longitudes autour de 2 à 7 pour Auvergne-Rhone-Alpes ;
- si ces ordres de grandeur sont inverses, les colonnes latitude/longitude sont probablement inversees ;
- vérifier les valeurs `minLat`, `maxLat`, `minLon`, `maxLon`, le centre et le zoom dans le panneau "Debug carte".

Si la carte semble vide :

- vérifier que `points_avec_coordonnees` est non nul dans le panneau debug ;
- vérifier que `const points` contient des nombres JSON pour `lat` et `lon`, pas des chaînes ;
- régénérer uniquement la carte avec `render-map` pour éviter une nouvelle résolution longue.

## Limites

- La carte est un export de contrôle, pas une source de vérité.
- Les alertes affichées sont non bloquantes.
- Le fond de carte depend d'un accès réseau àu service WMTS externe.
