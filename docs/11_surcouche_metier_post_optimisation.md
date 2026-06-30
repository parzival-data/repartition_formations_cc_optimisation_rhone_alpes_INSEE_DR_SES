# Surcouche métier post-optimisation

## Objectif

La commande `postprocess-business-rules` ajoute une étape optionnelle après la
résolution. Elle relit les exports produits par l'optimisation, détecte des
situations qui peuvent sembler étonnantes d'un point de vue métier, puis écrit
des propositions d'ajustement dans des fichiers séparés.

Cette étape ne relance pas le solveur, ne minimise pas une nouvelle fonction
objectif et ne modifie jamais les fichiers d'origine. La solution optimisée
reste la référence. Les sorties du post-traitement sont des suggestions à
examiner par les agents métier, pas des décisions automatiques.

## Commande

```powershell
cc-formation-optimizer postprocess-business-rules --config config/config_ear2027.yaml --input-dir outputs --output-dir outputs/postprocess
```

Le dossier `--input-dir` doit contenir les exports habituels :

- `solutions/sessions.csv` ;
- `solutions/communes_affectees.csv`.

La commande rechargé aussi les temps de trajet configurés dans le YAML afin de
comparer les pivots possibles. Le seuil minimal de gain pour les rattachements à
un autre pivot de même type est configurable :

```powershell
cc-formation-optimizer postprocess-business-rules --config config/config_ear2027.yaml --input-dir outputs --output-dir outputs/postprocess --min-travel-time-gain-min 5
```

La sortie terminale explicite les fichiers produits :

```text
Business post-processing completed.
Proposals written to: outputs/postprocess/business_reallocation_proposals.csv
Summary written to: outputs/postprocess/business_reallocation_summary.csv
Original optimization exports were not modified.
```

## Où trouver les résultats de la surcouche ?

Après exécution de la commande :

```bash
cc-formation-optimizer postprocess-business-rules \
  --config config/config_ear2027.yaml \
  --input-dir outputs \
  --output-dir outputs/postprocess \
  --min-travel-time-gain-min 5
```

les résultats métier sont écrits dans :

- `outputs/postprocess/business_reallocation_proposals.csv`
- `outputs/postprocess/business_reallocation_summary.csv`

Le premier fichier contient les propositions détaillées de changement. Le second
fichier contient une synthèse par règle. Les fichiers produits par
l'optimisation initiale ne sont pas modifiés.

## Fichiers produits

Deux fichiers CSV sont écrits dans le dossier de sortie :

- `business_reallocation_proposals.csv` : liste détaillée des propositions ;
- `business_reallocation_summary.csv` : synthèse par règle métier.

Les propositions contiennent notamment la règle appliquée, la session actuelle,
la commune concernée, le pivot proposé, les temps de trajet avant/après, les
chargés en CC avant/après, les gains potentiels, un indicateur de compatibilité
avec les contraintes du modèle et un commentaire métier.

La colonne `model_constraints_respected` indique si la proposition semble rester
compatible avec les contraintes vérifiables depuis les exports et la
configuration : capacité, seuil de trajet, compatibilité éventuelle et
interdiction d'affecter une commune PC à une session TPC. Une proposition non
compatible est conservée, mais la colonne `warning` explique la limite détectée.

## Règles métier

### Règle 1 : pivot interne pour les formations TPC

Pour chaque session TPC, la surcouche vérifie si le pivot actuel fait partie des
communes affectées à cette session. Si le pivot est externe, elle cherche parmi
les communes de la session un pivot interne qui minimise le temps de trajet total
des communes participantes. Les égalités sont départagées par le temps maximal,
puis par la population disponible, puis par le code commune.

La proposition change uniquement le pivot suggéré. Elle ne déplace aucune
commune.

### Règle 2 : rattacher une commune pivot à sa propre formation

Pour chaque session, la surcouche vérifie si la commune pivot participe à cette
session ou à une autre session dont elle est également pivot. Si ce n'est pas le
cas, elle propose de retirer cette commune de sa session actuelle et de la
rattacher à la session dont elle est pivot.

Cette proposition peut dépasser une contrainte du modèle, par exemple la
capacité maximale de la session cible ou le remplissage minimal de la session
source après retrait. Elle est tout de même écrite pour permettre un arbitrage
métier explicite.

### Règle 3 : commune plus proche d'un autre pivot de même type

Pour chaque commune affectée, la surcouche compare le pivot actuel avec les
autres pivots ouverts du même type de session, PC ou TPC. Si une autre session de
même type présente un temps de trajet strictement plus faible, et si le gain est
au moins égal àu seuil configuré, une proposition de rattachement est produite.

Cette règle ne compare pas les sessions de types différents. Une commune plus
proche d'un pivot TPC ne générera donc pas de proposition si elle est actuellement
dans une session PC.

## Conflits entre propositions

Les propositions sont indépendantes. La surcouche ne cherche pas à construire une
nouvelle solution complète et ne résout pas les conflits entre règles.

La colonne `conflict_hint` signale les cas où une même commune ou une même
session apparaît dans plusieurs propositions. Ces situations nécessitent un
arbitrage métier avant toute modification manuelle de la solution.

## Limites

Le post-traitement travaille à partir des exports et des temps de trajet
disponibles. Il ne connaît pas toutes les intentions métier qui peuvent expliquer
une solution optimisée. Il ne remplace donc ni la validation du modèle, ni la
validation métier finale.

Les cohérences territoriales sont signalées dans les exports principaux comme
des alertes, mais elles ne constituent pas une contrainte dure du modèle actuel.
La surcouche ne les transforme pas en interdiction automatique.

Enfin, une proposition peut être localement séduisante tout en dégradant une
autre partie de la solution. C'est pourquoi aucun ajustement n'est appliqué
automatiquement.
