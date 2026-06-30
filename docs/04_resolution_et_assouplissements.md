# Résolution et àssouplissements

La résolution cible suit quatre étapes.

## Diagnostic pré-résolution

Avant tout appel solveur, le projet doit identifier :

- les communes sans pivot atteignable ;
- les communes PC sans pivot atteignable et compatible pour une session PC ;
- la borne minimale de formations au regard du volume total de CC et de `Q` ;
- la cohérence declarative des budgets.

Le diagnostic actuel ne calculé pas explicitement des zones TPC isolées. Les
cas TPC difficiles sont observes indirectement via les communes orphelines, les
trajets admissibles et les résultats du solveur.

## Construction du modèle

Le modèle CP-SAT est implémenté dans `model_builder.py`. Les variables `x_ijm` sont creees uniquement si le trajet est admissible et compatible : `a_ij = 1` et `b_ij = 1`.

## Résolution

OR-Tools CP-SAT est utilisé avec les paramètres solveur configurés dans le YAML : temps limite, nombre de workers, graine aléatoire et logs. La fonction `solve_model` retourne le statut, la valeur d'objectif si disponible, le solveur et le temps de résolution.

## Assouplissements

La hiérarchie d'assouplissement est implémentée dans `relaxation.py` et accessible avec :

```bash
cc-formation-optimizer solve-relaxed --config config/config_ear2027.yaml
```

`solve` doit être utilisé pour résoudre strictement la configuration fournie. `solve-relaxed` doit être utilisé lorsque l'on veut appliquer le protocole reproductible d'assouplissement après un échec, sans modifier silencieusement les règles métier.

Ordre des niveaux :

1. configuration initiale ;
2. ajustement de `w_m` ;
3. reduction des coûts `e_j_TPC` ;
4. augmentation de l'unique paramètre `T` ;
5. reduction de `L` ;
6. augmentation de `Q` ;
7. augmentation coherente des budgets `f`, `k`, `B` avec `B = f + k` ;
8. remplacement explicite des coûts très élevés par une pénalité finie configurée.

À chaque tentative, une copie indépendante de la configuration initiale est modifiée, puis toute la chaîne est relancée : paramètres dérivés, modèle CP-SAT, solveur, extraction, validation. Le processus s'arrête à la première solution validée.

La contrainte stricte PC -> session TPC n'est jamais relâchée automatiquement. Si cette contrainte bloque une zone, il s'agit d'une décision métier à remonter explicitement, pas d'un paramètre assoupli par le protocole standard.

Les fichiers de suivi sont :

- `outputs/reports/journal_assouplissements.json` ;
- `outputs/reports/rapport_assouplissements.md` ;
- `outputs/reports/config_finale.yaml` si une solution validée est trouvée.

Le journal JSON contient pour chaque tentative le niveau, les paramètres modifiés, le statut solveur, le statut validation, les composantes d'objectif et le temps de calcul.
