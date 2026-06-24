# Resolution et assouplissements

La resolution cible suit quatre etapes.

## Diagnostic pre-resolution

Avant tout appel solveur, le projet doit identifier :

- les communes sans pivot atteignable ;
- les communes PC sans pivot atteignable et compatible pour une session PC ;
- la borne minimale de formations au regard du volume total de CC et de `Q` ;
- la coherence declarative des budgets.

Le diagnostic actuel ne calcule pas explicitement des zones TPC isolees. Les
cas TPC difficiles sont observes indirectement via les communes orphelines, les
trajets admissibles et les resultats du solveur.

## Construction du modele

Le modele CP-SAT est implemente dans `model_builder.py`. Les variables `x_ijm` sont creees uniquement si le trajet est admissible et compatible : `a_ij = 1` et `b_ij = 1`.

## Resolution

OR-Tools CP-SAT est utilise avec les parametres solveur configures dans le YAML : temps limite, nombre de workers, graine aleatoire et logs. La fonction `solve_model` retourne le statut, la valeur d'objectif si disponible, le solveur et le temps de resolution.

## Assouplissements

La hierarchie d'assouplissement est implementee dans `relaxation.py` et accessible avec :

```bash
cc-formation-optimizer solve-relaxed --config config/config_ear2027.yaml
```

`solve` doit etre utilise pour resoudre strictement la configuration fournie. `solve-relaxed` doit etre utilise lorsque l'on veut appliquer le protocole reproductible d'assouplissement apres un echec, sans modifier silencieusement les regles metier.

Ordre des niveaux :

1. configuration initiale ;
2. ajustement de `w_m` ;
3. reduction des couts `e_j_TPC` ;
4. augmentation de l'unique parametre `T` ;
5. reduction de `L` ;
6. augmentation de `Q` ;
7. augmentation coherente des budgets `f`, `k`, `B` avec `B = f + k` ;
8. remplacement explicite des couts tres eleves par une penalite finie configuree.

A chaque tentative, une copie independante de la configuration initiale est modifiee, puis toute la chaine est relancee : parametres derives, modele CP-SAT, solveur, extraction, validation. Le processus s'arrete a la premiere solution validee.

La contrainte stricte PC -> session TPC n'est jamais relachee automatiquement. Si cette contrainte bloque une zone, il s'agit d'une decision metier a remonter explicitement, pas d'un parametre assoupli par le protocole standard.

Les fichiers de suivi sont :

- `outputs/reports/journal_assouplissements.json` ;
- `outputs/reports/rapport_assouplissements.md` ;
- `outputs/reports/config_finale.yaml` si une solution validee est trouvee.

Le journal JSON contient pour chaque tentative le niveau, les parametres modifies, le statut solveur, le statut validation, les composantes d'objectif et le temps de calcul.
