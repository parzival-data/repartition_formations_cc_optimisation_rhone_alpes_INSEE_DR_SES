# Modélisation mathématique

Cette documentation reprend la formulation de référence.

## Ensembles

- `C` : ensemble des communes à affecter.
- `P` : ensemble des communes PC.
- `T` : ensemble des communes TPC.
- `F = C` : toute commune est candidate pivot.
- `S = {(j,m) : j in F, m in 1..M_j}` : slots de formation.

Les slots sont definis par :

- `M_j = 3` pour un pivot PC ;
- `M_j = 1` pour un pivot TPC.

## Paramètres

- `q_i` : nombre de CC à former pour la commune `i`.
- `tau_ij` : temps de trajet de `i` vers `j`.
- `T` : temps de trajet maximal autorisé.
- `Q` : capacité maximale d'une formation.
- `L` : remplissage minimal d'une formation ouverte.
- `f` : nombre maximal de formations ouvertes de type PC.
- `k` : nombre maximal de formations ouvertes de type TPC.
- `B = f + k` : nombre total maximal de formations.
- `e_j^PC`, `e_j^TPC` : coûts d'éligibilité du pivot.
- `w_t`, `w_e`, `w_m` : poids de l'objectif.

## Variables

- `x_ijm in {0,1}` : commune `i` affectée à la formation `(j,m)`.
- `y_jm in {0,1}` : formation `(j,m)` ouverte.
- `z_jm in {0,1}` : formation `(j,m)` déclarée de type TPC si `1`, de type PC si `0`.
- `d_jm in N` : écart de mixité.

## Objectif

Minimiser :

```text
w_t * Obj_trajet + w_e * Obj_eligibilite + w_m * Obj_mixite
```

avec :

```text
Obj_trajet = sum_i,j,m q_i * tau_ij * x_ijm
Obj_eligibilite = sum_j,m e_j^PC * y_jm + (e_j^TPC - e_j^PC) * z_jm
Obj_mixite = sum_j,m d_jm
```

## Contraintes

Les contraintes suivantes sont implémentées dans `model_builder.py` :

1. affectation unique de chaque commune ;
2. pas d'affectation sans ouverture ;
3. admissibilite `a_ij` et compatibilité `b_ij` integrees à la génération des variables ;
4. capacité et remplissage minimal ;
5. cohérence `z_jm <= y_jm` ;
6. budgets `sum(y_jm - z_jm) <= f` et `sum(z_jm) <= k` ;
7. ordre d'ouverture des formations pour les pivots PC ;
8. asymétrie stricte PC -> TPC ;
9. définition de la mixité résiduelle ;
10. domaines des variables.

Les variables `x_ijm` ne sont creees que pour les couples `(i,j)` admissibles et compatibles. Un trajet absent de la matrice `tau` ne cree donc aucune variable d'affectation.

La formulation CP-SAT reste linéaire : le coût d'éligibilité utilise `e_j^PC * y_jm + (e_j^TPC - e_j^PC) * z_jm`, et le budget PC utilise `y_jm - z_jm`. Aucun produit entre variables n'est introduit.

Après résolution, `solution_extractor.py` transforme les valeurs CP-SAT en sessions ouvertes et affectations de communes. `validation.py` recalculé ensuite les contraintes et les composantes d'objectif depuis cette solution métier avant toute exploitation.
