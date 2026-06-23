# Modelisation mathematique

Cette documentation reprend la formulation de reference.

## Ensembles

- `C` : ensemble des communes a affecter.
- `P` : ensemble des communes PC.
- `T` : ensemble des communes TPC.
- `F = C` : toute commune est candidate pivot.
- `S = {(j,m) : j in F, m in 1..M_j}` : slots de formation.

Les slots sont definis par :

- `M_j = 3` pour un pivot PC ;
- `M_j = 1` pour un pivot TPC.

## Parametres

- `q_i` : nombre de CC a former pour la commune `i`.
- `tau_ij` : temps de trajet de `i` vers `j`.
- `T` : temps de trajet maximal autorise.
- `Q` : capacite maximale d'une formation.
- `L` : remplissage minimal d'une formation ouverte.
- `f` : nombre maximal de formations ouvertes de type PC.
- `k` : nombre maximal de formations ouvertes de type TPC.
- `B = f + k` : nombre total maximal de formations.
- `e_j^PC`, `e_j^TPC` : couts d'eligibilite du pivot.
- `w_t`, `w_e`, `w_m` : poids de l'objectif.

## Variables

- `x_ijm in {0,1}` : commune `i` affectee a la formation `(j,m)`.
- `y_jm in {0,1}` : formation `(j,m)` ouverte.
- `z_jm in {0,1}` : formation `(j,m)` declaree de type TPC si `1`, de type PC si `0`.
- `d_jm in N` : ecart de mixite.

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

Les contraintes seront implementees dans `model_builder.py` lors de l'etape solveur :

1. affectation unique de chaque commune ;
2. pas d'affectation sans ouverture ;
3. admissibilite `a_ij` et compatibilite `b_ij` integrees a la generation des variables ;
4. capacite et remplissage minimal ;
5. coherence `z_jm <= y_jm` ;
6. budgets `sum(y_jm - z_jm) <= f` et `sum(z_jm) <= k` ;
7. ordre d'ouverture des formations pour les pivots PC ;
8. asymetrie stricte PC -> TPC ;
9. definition de la mixite residuelle ;
10. domaines des variables.
