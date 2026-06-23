# Resolution et assouplissements

La resolution cible suit quatre etapes.

## Diagnostic pre-resolution

Avant tout appel solveur, le projet doit identifier :

- les communes sans pivot atteignable ;
- les communes PC sans pivot atteignable pouvant porter une formation PC ;
- les zones TPC isolees qui peuvent necessiter un pivot promu.

## Construction du modele

Le modele CP-SAT est implemente dans `model_builder.py`. Les variables `x_ijm` sont creees uniquement si le trajet est admissible et compatible : `a_ij = 1` et `b_ij = 1`.

## Resolution

OR-Tools CP-SAT est utilise avec les parametres solveur configures dans le YAML : temps limite, nombre de workers, graine aleatoire et logs. La fonction `solve_model` retourne le statut, la valeur d'objectif si disponible, le solveur et le temps de resolution.

## Assouplissements

La hierarchie d'assouplissement est configuree mais pas encore implementee. La contrainte d'asymetrie stricte PC -> TPC ne fait pas partie des assouplissements automatiques.

Les exports finaux detailles seront ajoutes dans une etape ulterieure.
